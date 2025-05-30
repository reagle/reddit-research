#!/usr/bin/env python3
"""Message Redditors listed in CSV.

Message Redditors using CSV files from with usernames in column
`author_p`. Can take output of reddit-query or reddit-watch
and select users for messaging based on attributes (e.g., throwaway,
deleted, or already messaged).".
"""

__author__ = "Joseph Reagle"
__copyright__ = "Copyright (C) 2021-2023 Joseph Reagle"
__license__ = "GLPv3"
__version__ = "1.0"

import argparse  # http://docs.python.org/dev/library/argparse.html
import csv
import logging as log
import sys
import time
from pathlib import Path

import arrow  # https://arrow.readthedocs.io/en/latest/
import pandas as pd
import praw  # https://praw.readthedocs.io/en/latest
import tqdm  # progress bar https://github.com/tqdm/tqdm
from praw.exceptions import RedditAPIException

from reddit_research import web_utils

REDDIT = praw.Reddit(
    user_agent=web_utils.get_credential("REDDIT_USER_AGENT"),
    client_id=web_utils.get_credential("REDDIT_CLIENT_ID"),
    client_secret=web_utils.get_credential("REDDIT_CLIENT_SECRET"),
    username=web_utils.get_credential("REDDIT_USERNAME"),
    password=web_utils.get_credential("REDDIT_PASSWORD"),
    ratelimit_seconds=600,
)


NOW = arrow.utcnow()
NOW_STR = NOW.format("YYYYMMDD HH:mm:ss")


def is_throwaway(user_name: str) -> bool:
    """Return True if the username is a throwaway."""
    name = user_name.lower()
    return ("throw" in name and "away" in name) or ("throwra" in name)


def select_users(args: argparse.Namespace, df: pd.DataFrame) -> set[str]:
    """Select users based on arguments and DataFrame."""
    users_found = set()
    users_del = set()
    users_throw = set()
    for _, row in df.iterrows():
        users_found.add(row["author_p"])
        log.warning(f'{row["author_p"]=}')
        if is_throwaway(str(row["author_p"])):
            log.warning("  adding to users_throw")
            users_throw.add(row["author_p"])
        if row["del_author_p"] is False and row["del_text_r"] is True:
            log.warning("  adding to users_del")
            users_del.add(row["author_p"])
    users_result = users_found.copy()
    print("Users' statistics:")
    print(f"  {len(users_found)= :4}")
    print(f"  {len(users_del)=   :4}  {len(users_del) / len(users_found):2.0%}")
    print(f"  {len(users_throw)= :4}  {len(users_throw) / len(users_found):2.0%}")
    print(
        f"  {len(users_del & users_throw)=}"
        + f"  {len(users_del & users_throw) / len(users_found):2.0%} of found;"
        + f"  {len(users_del & users_throw) / len(users_throw):2.0%} of throwaway"
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
    """Maintain a set of users who have been messaged."""

    def __init__(self, archive_fn: Path, dry_run: bool) -> None:
        self.dry_run = dry_run
        self.archive_fn = archive_fn
        users_past_d = {}
        if not archive_fn.exists():
            archive_fn.write_text("name,timestamp\n", encoding="utf-8")
        csv_reader = csv.DictReader(archive_fn.open(encoding="utf-8"))
        for row in csv_reader:
            users_past_d[row["name"]] = row["timestamp"]
        self.users_past = set(users_past_d.keys())

    def get(self) -> set:
        return self.users_past

    def update(self, user: str) -> None:
        if not self.dry_run and user not in self.users_past:
            self.users_past.add(user)
            with self.archive_fn.open("a", encoding="utf-8") as past_fd:
                csv_writer = csv.DictWriter(past_fd, fieldnames=["name", "timestamp"])
                csv_writer.writerow({"name": user, "timestamp": NOW_STR})


def message_users(
    args: argparse.Namespace, users: set[str], subject: str, greeting: str
) -> None:
    """Message users."""
    user_archive = UsersArchive(args.archive_fn, args.dry_run)
    users_past = user_archive.get()
    users_todo = users - users_past
    print(f"\nExcluding {len(users_past)} past users from the {len(users)}.")
    if args.show_csv_users:
        print(f"The remaining {len(users_todo)} users to do are: {users_todo}.")

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


def process_args(argv: list[str]) -> argparse.Namespace:
    """Process command-line arguments."""
    arg_parser = argparse.ArgumentParser(
        description=(
            "Message Redditors using CSV files with usernames in column"
            " `author_p`. Can take output of reddit-query or reddit-watch and"
            " select users for messaging based on attributes."
        ),
    )

    arg_parser.add_argument(
        "-i",
        "--input-fn",
        metavar="FILENAME",
        required=True,
        type=Path,
        help="CSV filename, with usernames, created by reddit-query",
    )
    arg_parser.add_argument(
        "-a",
        "--archive-fn",
        default=Path("reddit-message-users-past.csv"),
        metavar="FILENAME",
        required=False,
        type=Path,
        help=(
            "CSV filename of previously messaged users to skip;"
            + " created if doesn't exist"
            + " (default: %(default)s)"
        ),
    )
    arg_parser.add_argument(
        "-g",
        "--greeting-fn",
        default=Path("greeting.txt"),
        metavar="FILENAME",
        required=False,
        type=Path,
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
        help="increase verbosity from critical though error, warning, info, and debug",
    )

    arg_parser.add_argument("--version", action="version", version="0.3")
    args = arg_parser.parse_args(argv)

    log_level = (log.CRITICAL) - (args.verbose * 10)
    LOG_FORMAT = "%(levelname).4s %(funcName).10s:%(lineno)-4d| %(message)s"
    if args.log_to_file:
        print("logging to file")
        log.basicConfig(
            filename=Path(__file__).with_suffix(".log"),
            filemode="w",
            level=log_level,
            format=LOG_FORMAT,
        )
    else:
        log.basicConfig(level=log_level, format=LOG_FORMAT)

    return args


def main() -> None:
    """Process arguments and call functions."""
    args = process_args(sys.argv[1:])
    log.info(f"Parsed arguments: {args}")

    for fn in (args.input_fn, args.greeting_fn):
        if not fn.exists():
            raise RuntimeError(f"Necessary file {fn} does not exist")

    with args.greeting_fn.open() as fd:
        greeting_lines = fd.readlines()
        if greeting_lines[0].lower().startswith("subject: "):
            subject = greeting_lines[0][9:].strip()
            greeting = "".join(greeting_lines[1:]).strip()
        else:
            subject = "About your Reddit message"
            greeting = "".join(greeting_lines).strip()
    greeting_trunc = greeting.replace("\n", " ")[:70]

    df = pd.read_csv(args.input_fn, comment="#")
    log.info(f"The input CSV file contains {df.shape[0]} rows.")

    if {"author_p", "del_author_p", "del_text_r"}.issubset(df.columns):
        log.info(
            "Unique and not-previously messaged users will be further winnowed by:"
        )
        log.info(f"  args.only_deleted   = {args.only_deleted}")
        log.info(f"  args.only_existent  = {args.only_existent}")
        log.info(f"  args.only_pseudonym = {args.only_pseudonym}")
        log.info(f"  args.only_throwaway = {args.only_throwaway}")
        users = select_users(args, df)
    elif "author_p" in df and not any(
        [
            args.only_deleted,
            args.only_existent,
            args.only_pseudonym,
            args.only_throwaway,
        ]
    ):
        log.info(
            "Messaging without delete, existent, pseudonym, and throwaway selection."
        )
        users = set(df["author_p"])
    else:
        raise KeyError("One or more columns are missing from the CSV DataFrame.")

    log.info(
        f"\nYou will be sending:\n  Subject: {subject}\n  Greeting: {greeting_trunc}..."
    )

    if not args.dry_run:
        proceed_q = input("Do you want to proceed? `p` to proceed | any key to quit: ")
        if proceed_q != "p":
            sys.exit()
        if not args.only_existent or args.only_deleted:
            confirm_q = input(
                "WARNING: you might be messaging users who deleted their messages. `c` to confirm | any key to quit: "
            )
            if confirm_q != "c":
                sys.exit()
    message_users(args, users, subject, greeting)


if __name__ == "__main__":
    main()
