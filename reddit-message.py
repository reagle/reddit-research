#!/usr/bin/env python3
"""Message Redditors.

Obtain Redditor usernames from a CSV file and message those who fit
criteria of throwaway or not, or deleted their post.
Do not messages users messaged in the past.
"""

__author__ = "Joseph Reagle"
__copyright__ = "Copyright (C) 2021-2023 Joseph Reagle"
__license__ = "GLPv3"
__version__ = "1.0"

# TODO
# - perhaps make the exclusion of past users a command line argument
#   and refactor it as a feature of select_users() 2022-07-27

import argparse  # http://docs.python.org/dev/library/argparse.html
import csv
import logging
import os
import pathlib as pl
import sys
import time

import pandas as pd
import pendulum  # https://pendulum.eustace.io/docs/
import praw  # https://praw.readthedocs.io/en/latest
import tqdm  # progress bar https://github.com/tqdm/tqdm
from praw.exceptions import RedditAPIException

import web_api_tokens as wat

# https://github.com/pushshift/api
# import psaw  # Pushshift API https://github.com/dmarx/psaw no exclude:not

REDDIT = praw.Reddit(
    user_agent=wat.REDDIT_USER_AGENT,
    client_id=wat.REDDIT_CLIENT_ID,
    client_secret=wat.REDDIT_CLIENT_SECRET,
    username=wat.REDDIT_USERNAME,
    password=wat.REDDIT_PASSWORD,
    ratelimit_seconds=600,
)
NOW = pendulum.now("UTC")
NOW_STR = NOW.format("YYYYMMDD HH:mm:ss")

exception = logging.exception
critical = logging.critical
error = logging.error
warning = logging.warning
info = logging.info
debug = logging.debug


# this is duplicated in reddit-query.py and reddit-message.py
def is_throwaway(user_name: str) -> bool:
    name = user_name.lower()
    # "throwra" is common throwaway in (relationship) advice subreddits
    return ("throw" in name and "away" in name) or ("throwra" in name)


def select_users(args, df) -> set[str]:
    """Return a list of users fitting criteria
    - only_deleted: deleted on Reddit
    - only_existent: NOT deleted
    - only_throwaway: "throw" and "away" appears in username
    - only_pseudo: NOT throwaway"""
    users_found = set()
    users_del = set()
    users_throw = set()
    for _, row in df.iterrows():
        users_found.add(row["author_p"])
        warning(f'{row["author_p"]=}')
        if is_throwaway(row["author_p"]):
            warning("  adding to users_throw")
            users_throw.add(row["author_p"])
        if row["del_author_p"] is False and row["del_text_r"] is True:
            warning("  adding to users_del")
            users_del.add(row["author_p"])
    users_result = users_found.copy()
    print("Users' statistics:")
    print(f"  {len(users_found)= :4}")
    print(f"  {len(users_del)=   :4}  {len(users_del)/len(users_found):2.0%}")
    print(f"  {len(users_throw)= :4}  {len(users_throw)/len(users_found):2.0%}")
    print(
        f"  {len(users_del & users_throw)=}"
        + f"  {len(users_del & users_throw)/len(users_found):2.0%} of found;"
        + f"  {len(users_del & users_throw)/len(users_throw):2.0%} of throwaway"
    )
    if args.only_deleted:
        users_result = users_result & users_del
    if args.only_existent:
        users_result = users_result - users_del
    if args.only_throwaway:
        users_result = users_result & users_throw
    if args.only_pseudonym:
        users_result = users_result - users_throw
    print(f"\nYou are about to message {len(users_result)} possible unique users.")
    if args.show_csv_users:
        print(f"They are: {users_result}")

    return users_result


class UsersArchive:
    """A persistent set-like store plaintext/csv back-end."""

    def __init__(self, archive_fn: str) -> None:
        """Create file if it doesn't exist, otherwise read in."""
        self.archive_fn = archive_fn
        users_past_d = {}
        if not os.path.exists(archive_fn):
            with open(archive_fn, "w", encoding="utf-8") as past_fd:
                past_fd.write("name,timestamp\n")
        with open(archive_fn, encoding="utf-8") as past_fd:
            csv_reader = csv.DictReader(past_fd)
            for row in csv_reader:
                users_past_d[row["name"]] = row["timestamp"]
        self.users_past = set(users_past_d.keys())

    def get(self) -> set:
        return self.users_past

    def update(self, user: str) -> None:
        if not args.dry_run and user not in self.users_past:
            self.users_past.add(user)
            # TODO: I'm not worried about disk IO speed because of the network IO rate
            # limit but this still feels wasteful, can/should I keep the file
            # descriptor open across updates?
            with open(self.archive_fn, "a", encoding="utf-8") as past_fd:
                csv_writer = csv.DictWriter(past_fd, fieldnames=["name", "timestamp"])
                csv_writer.writerow({"name": user, "timestamp": NOW_STR})


def message_users(args, users: set[str], subject: str, greeting: str) -> None:
    """Post message to users, without repeating users"""

    user_archive = UsersArchive(args.archive_fn)
    users_past = user_archive.get()
    users_todo = users - users_past
    print(f"\nExcluding {len(users_past)} past users from the {len(users)}.")
    if args.show_csv_users:
        print(f"The remaining users to do are: {users_todo}.")

    with tqdm.tqdm(
        total=len(users_todo), bar_format="{l_bar}{bar:30}{r_bar}{bar:-10b}"
    ) as pbar:
        for user in users_todo:
            pbar.set_postfix({"user": user})
            user_archive.update(user)
            if not args.dry_run:
                try:
                    REDDIT.redditor(user).message(subject=subject, message=greeting)
                except RedditAPIException as error:
                    tqdm.tqdm.write(f"can't message {user}: {error} ")
                    if "RATELIMIT" in str(error):
                        raise error
                time.sleep(args.rate_limit)
            pbar.update()


def process_args(argv) -> argparse.Namespace:
    """Process arguments"""
    arg_parser = argparse.ArgumentParser(
        description=(
            "Message Redditors using CSV files from with usernames in column"
            " `author_p`. Can take output of reddit-query.py or reddit-watch.py and"
            " select users for messaging based on attributes."
        ),
    )

    # non-positional arguments
    arg_parser.add_argument(
        "-i",
        "--input-fn",
        metavar="FILENAME",
        required=True,
        help="CSV filename, with usernames, created by reddit-query.py",
    )
    arg_parser.add_argument(
        "-a",
        "--archive-fn",
        default="reddit-message-users-past.csv",
        metavar="FILENAME",
        required=False,
        help=(
            "CSV filename of previously messaged users to skip;"
            + " created if doesn't exist"
            + " (default: %(default)s)"
        ),
    )
    arg_parser.add_argument(
        "-g",
        "--greeting-fn",
        default="greeting.txt",
        metavar="FILENAME",
        required=False,
        help="greeting message filename (default: %(default)s)",
    )
    arg_parser.add_argument(
        "-d",
        "--only-deleted",
        action="store_true",
        default=False,
        help="select deleted users only",
    )
    arg_parser.add_argument(
        "-e",
        "--only-existent",
        action="store_true",
        default=False,
        help="select existent (NOT deleted) users only",
    )
    arg_parser.add_argument(
        "-p",
        "--only-pseudonym",
        action="store_true",
        default=False,
        help="select pseudonyms only (NOT throwaway)",
    )
    arg_parser.add_argument(
        "-t",
        "--only-throwaway",
        action="store_true",
        default=False,
        help="select throwaway accounts only ('throw' and 'away')",
    )
    arg_parser.add_argument(
        "-r",
        "--rate-limit",
        type=int,
        default=40,
        help="rate-limit in seconds between messages (default: %(default)s)",
    )
    arg_parser.add_argument(
        "-s",
        "--show-csv-users",
        action="store_true",
        default=False,
        help="also show all users from input CSV on terminal",
    )

    arg_parser.add_argument(
        "-D",
        "--dry-run",
        action="store_true",
        default=False,
        help="list greeting and users but don't message",
    )
    arg_parser.add_argument(
        "-L",
        "--log-to-file",
        action="store_true",
        default=False,
        help="log to file %(prog)s.log",
    )
    arg_parser.add_argument(
        "-V",
        "--verbose",
        action="count",
        default=0,
        help="increase logging verbosity (specify multiple times for more)",
    )

    arg_parser.add_argument("--version", action="version", version="0.3")
    args = arg_parser.parse_args(argv)

    log_level = logging.ERROR  # 40

    if args.verbose == 1:
        log_level = logging.WARNING  # 30
    elif args.verbose == 2:
        log_level = logging.INFO  # 20
    elif args.verbose >= 3:
        log_level = logging.DEBUG  # 10
    LOG_FORMAT = "%(levelname).3s %(funcName).5s: %(message)s"
    if args.log_to_file:
        print("logging to file")
        logging.basicConfig(
            filename=f"{str(pl.PurePath(__file__).name)}.log",
            filemode="w",
            level=log_level,
            format=LOG_FORMAT,
        )
    else:
        logging.basicConfig(level=log_level, format=LOG_FORMAT)

    return args


if __name__ == "__main__":
    args = process_args(sys.argv[1:])

    info(f"{args=}")
    for fn in (args.input_fn, args.greeting_fn):
        if not os.path.exists(fn):
            raise RuntimeError(f"necessary file {fn} does not exist")
    with open(args.greeting_fn) as fd:
        greeting = fd.readlines()
        if greeting[0].lower().startswith("subject: "):
            subject = greeting[0][9:].strip()
            greeting = "".join(greeting[1:]).strip()
        else:
            subject = "About your Reddit message"
            greeting = "".join(greeting).strip()
    greeting_trunc = greeting.replace("\n", " ")[0:70]

    df = pd.read_csv(args.input_fn)
    print(f"The input CSV file contains {df.shape[0]} rows.")
    if {"author_p", "del_author_p", "del_text_r"}.issubset(df.columns):
        print(
            "Unique and not-previously messaged users will be further winnowed by:\n"
            + f"  args.only_deleted   = {args.only_deleted}\n"
            + f"  args.only_existent  = {args.only_existent}\n"
            + f"  args.only_pseudonym = {args.only_pseudonym}\n"
            + f"  args.only_throwaway = {args.only_throwaway}\n"
        )
        users = select_users(args, df)
    elif "author_p" in df and not any(
        [
            args.only_deleted,
            args.only_existent,
            args.only_pseudonym,
            args.only_throwaway,
        ]
    ):
        print("Messaging without delete, existent, pseudonym, and throwaway selection")
        users = set(df["author_p"])
    else:
        raise KeyError("One or more columns are missing from the CSV DataFrame.")

    print(
        "\nYour will be sending:\n"
        + f"  Subject: {subject}\n"
        + f"  Greeting: {greeting_trunc}..."
    )

    if not args.dry_run:
        print("Do you want to proceed?")
        proceed_q = input("`p` to proceed | any key to quit: ")
        if proceed_q == "p":
            pass
        else:
            sys.exit()
        if not args.only_existent or args.only_deleted:
            print("WARNING: you might be messaging users who deleted their messages.")
            confirm_q = input("`c` to confirm | any key to quit: ")
            if confirm_q == "c":
                pass
            else:
                sys.exit()
    message_users(args, users, subject, greeting)
