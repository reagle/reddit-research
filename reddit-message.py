#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# DESCRIPTION
# This file is part of Reddit Tools
# <https://github.com/reagle/reddit/>
# (c) Copyright 2020-2022 by Joseph Reagle
# Licensed under the GPLv3, see <http://www.gnu.org/licenses/gpl-3.0.html>

"""
Obtain Redditor usernames from a CSV file and message those who fit criteria
of throwaway or not, or deleted their post.
Do not messages users messaged in the past.
"""

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


def is_throwaway(user_name: str) -> bool:
    user_name = user_name.lower()
    return "throw" in user_name and "away" in user_name


def select_users(args, df) -> set[str]:
    """Return a list of users who deleted post (and, optionally, throwaway)"""
    users = set()
    users_del = set()
    users_throw = set()
    for _counter, row in df.iterrows():
        users.add(row["author_p"])
        warning(f'{row["author_p"]=}')
        if is_throwaway(row["author_p"]):
            warning("  adding to users_throw")
            users_throw.add(row["author_p"])
        if row["del_author_p"] is False and row["del_text_r"] is True:
            warning("  adding to users_del")
            users_del.add(row["author_p"])
    users_del_throw = users_del & users_throw
    info(f"{users_del_throw=}")
    users_pseudo = users - users_throw
    info(f"{users_pseudo=}")
    users_del_pseudo = users_pseudo & users_del
    info(f"{users_del_pseudo=}")
    print(f"posts={df.shape[0]=}")
    print(f"{len(users)=}")
    print(f"{len(users_del)=}  {len(users_del)/len(users):2.0%}")
    print(f"{len(users_throw)=}  {len(users_throw)/len(users):2.0%}")
    print(f"{len(users_del_throw)=}  {len(users_del_throw)/len(users_throw):2.0%}")
    print(f"{len(users_pseudo)=}  {len(users_pseudo)/len(users):2.0%}")
    print(f"{len(users_del_pseudo)=}  {len(users_del_pseudo)/len(users):2.0%}")
    if args.deleted and args.throwaway_only:
        return users_del_throw
    if args.deleted and args.pseudonyms_only:
        return users_del_pseudo
    if args.deleted:
        return users_del
    if args.throwaway_only:
        return users_throw
    if args.pseudonyms_only:
        return users_pseudo
    return users


class UsersArchive:
    def __init__(self, archive_fn: str) -> None:
        users_past_d = {}
        self.archive_fn = archive_fn
        if not os.exists(archive_fn):
            with open(archive_fn, "w", encoding="utf-8") as past_fd:
                past_fd.write("name,timestamp")
        with open(archive_fn, "r", encoding="utf-8") as past_fd:
            csv_reader = csv.DictReader(past_fd)
            for row in csv_reader:
                users_past_d[row["name"]] = row["timestamp"]
        self.users_past = set(users_past_d.keys())
        print(f"{self.users_past=}")

    def get(self):
        return self.users_past

    def update(self, user: str):
        if user not in self.users_past:
            self.users_past.add(user)
            # I'm not worried about disk IO speed because of the network IO rate limit
            # but this still feels wasteful, can/should I keep the file descriptor
            # open across updates?
            with open(self.archive_fn, "a", encoding="utf-8") as past_fd:
                csv_writer = csv.DictWriter(past_fd, fieldnames=["name", "timestamp"])
                csv_writer.writerow({"name": user, "timestamp": NOW_STR})


def message_users_2(args, users: set, greeting: str) -> None:
    """Post message to users, without repeating users"""

    PAST_USERS_FN = "/Users/reagle/bin/red/reddit-message-users-past.csv"
    RATE_LIMIT_SLEEP = 40

    user_archive = UsersArchive(PAST_USERS_FN)
    users_past = user_archive.get()
    users_todo = users - users_past

    for user in tqdm.tqdm(users_todo):
        user_archive.update(user)
        tqdm.tqdm.write(f"messaging user {user}")
        try:
            REDDIT.redditor(user).message("Deleted your post?", greeting)
        except praw.exceptions.RedditAPIException as error:
            tqdm.tqdm.write(f"can't message {user}: {error} ")
            if "RATELIMIT" in str(error):
                raise error
        time.sleep(RATE_LIMIT_SLEEP)


def message_users_1(args, users: set, greeting: str) -> None:
    """Post message to users, without repeating users"""

    RATE_LIMIT_SLEEP = 40
    PAST_USERS_FN = "/Users/reagle/bin/red/reddit-message-users-past.csv"
    users_past_d = {}

    if not os.exists(PAST_USERS_FN):
        with open(PAST_USERS_FN, "w", encoding="utf-8") as past_fd:
            past_fd.write("name,timestamp")

    with open(PAST_USERS_FN, "r", encoding="utf-8") as past_fd:
        csv_reader = csv.DictReader(past_fd)
        for row in csv_reader:
            users_past_d[row["name"]] = row["timestamp"]
    users_todo = users - set(users_past_d.keys())

    with open(PAST_USERS_FN, "a", encoding="utf-8") as past_fd:
        csv_writer = csv.DictWriter(past_fd, fieldnames=["name", "timestamp"])
        for user in tqdm.tqdm(users_todo):
            csv_writer.writerow({"name": user, "timestamp": NOW_STR})
            tqdm.tqdm.write(f"messaging user {user}")
            try:
                REDDIT.redditor(user).message("Deleted your post?", greeting)
            except praw.exceptions.RedditAPIException as error:
                tqdm.tqdm.write(f"can't message {user}: {error} ")
                if "RATELIMIT" in str(error):
                    raise error
            time.sleep(RATE_LIMIT_SLEEP)


def message_users(args, users: set, greeting: str) -> None:
    """Post message to users"""

    RATE_LIMIT_SLEEP = 40

    for user in tqdm(users):
        tqdm.write(f"messaging user {user}")
        try:
            REDDIT.redditor(user).message("Deleted your post?", greeting)
        except praw.exceptions.RedditAPIException as error:
            tqdm.write(f"can't fetch {user}: {error} ")
            if "RATELIMIT" in str(error):
                raise error
        time.sleep(RATE_LIMIT_SLEEP)


def main(argv) -> argparse.Namespace:
    """Process arguments"""
    arg_parser = argparse.ArgumentParser(description="Script for querying reddit APIs")

    # non-positional arguments
    arg_parser.add_argument(
        "-d",
        "--deleted",
        action="store_true",
        default=False,
        help="select deleted users",
    )
    arg_parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="list greeting and users but don't message",
    )
    arg_parser.add_argument(
        "-i",
        "--input-filename",
        metavar="FILENAME",
        nargs=1,
        required=True,
        help="input CSV file",
    )
    arg_parser.add_argument(
        "-g",
        "--greeting-filename",
        default="greeting.txt",
        metavar="FILENAME",
        help="input greeting file",
    )
    arg_parser.add_argument(
        "-p",
        "--pseudonyms_only",
        action="store_true",
        default=False,
        help="select pseudonyms only (non-throwaway)",
    )
    arg_parser.add_argument(
        "-s",
        "--show",
        action="store_true",
        default=False,
        help="show all users on terminal",
    )
    arg_parser.add_argument(
        "-t",
        "--throwaway-only",
        action="store_true",
        default=False,
        help="select throwaway accounts only ('throw' and 'away')",
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
    args = main(sys.argv[1:])

    with open(args.greeting_filename, "r") as fd:
        greeting = fd.read()
    df = pd.read_csv(args.input_filename[0])
    users = select_users(args, df)
    print(f"{len(users)} users to message")
    if args.show:
        print(f"message:\n{greeting[0:50]}...\n")
        print(f" {users=}")
    if not args.dry_run:
        message_users(args, users, greeting)
