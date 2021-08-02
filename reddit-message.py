#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# DESCRIPTION
# (c) Copyright 2020 by Joseph Reagle
# Licensed under the GPLv3, see <http://www.gnu.org/licenses/gpl-3.0.html>
#

"""
Message Redditors who still have their accounts and deleted their posts to an
advice subreddit.
Reads data from a CSV file.
"""

import argparse  # http://docs.python.org/dev/library/argparse.html
from typing import Any

# import datetime as dt
import logging

import pandas as pd

# import random
import sys
import time

# import time
from pathlib import PurePath

# from typing import Any, Tuple

# import numpy as np
# import pandas as pd

# https://www.reddit.com/dev/api/
import praw  # https://praw.readthedocs.io/en/latest

from tqdm import tqdm  # progress bar https://github.com/tqdm/tqdm

from web_api_tokens import (
    REDDIT_CLIENT_SECRET,
    REDDIT_CLIENT_ID,
    REDDIT_USER_AGENT,
    REDDIT_PASSWORD,
    REDDIT_USERNAME,
)

# https://github.com/reagle/thunderdell
# from web_utils import get_JSON

# https://github.com/pushshift/api
# import psaw  # Pushshift API https://github.com/dmarx/psaw no exclude:not

REDDIT = praw.Reddit(
    user_agent=REDDIT_USER_AGENT,
    client_id=REDDIT_CLIENT_ID,
    client_secret=REDDIT_CLIENT_SECRET,
    username=REDDIT_USERNAME,
    password=REDDIT_PASSWORD,
)

NOW = time.strftime("%Y%m%d", time.localtime())

exception = logging.exception
critical = logging.critical
error = logging.error
warning = logging.warning
info = logging.info
debug = logging.debug


def read_df(file_name) -> Any:
    """Retrun a dataframe given in a filename."""

    df.from_csv(f"{file_name}.csv", encoding="utf-8-sig", index=False)
    print(f"read dataframe of shape {df.shape} from '{file_name}.csv'")


def select_deleted_users(args, df) -> list[str]:
    """Return a list of users who match condition"""
    users = []
    for counter, row in df.iterrows():
        info(f'{row["author_p"]=}')
        # skip if args.throwaway and account isn't throwaway
        if args.throwaway_only and "throwaw" not in row["author_p"].lower():
            info("  skipping")
            continue
        # include if there's a mismatch and it's subsequently deleted
        if row["del_author_p"] is False and row["del_text_r"] is True:
            info("  adding")
            users.append(row["author_p"])
        else:
            info("  not deleted")
    return users


def message_users(args, users, greeting) -> None:
    """Post message to users"""

    RATE_LIMIT = 30
    for user in tqdm(users):
        tqdm.write(f"messaging user {user}")
        try:
            REDDIT.redditor(user).message("Deleted your post?", greeting)
        except praw.exceptions.RedditAPIException as error:
            tqdm.write(f"can't fetch {user}: {error} ")
            if "RATELIMIT" in str(error):
                raise error
        time.sleep(RATE_LIMIT)


def main(argv) -> argparse.Namespace:
    """Process arguments"""
    arg_parser = argparse.ArgumentParser(
        description="Script for querying reddit APIs"
    )

    # non-positional arguments
    arg_parser.add_argument(
        "-d",
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
        help="text of message",
    )
    arg_parser.add_argument(
        "-t",
        "--throwaway-only",
        action="store_true",
        default=False,
        help="message throway accounts only",
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
            filename=f"{str(PurePath(__file__).name)}.log",
            filemode="w",
            level=log_level,
            format=LOG_FORMAT,
        )
    else:
        logging.basicConfig(level=log_level, format=LOG_FORMAT)

    return args


if __name__ == "__main__":
    args = main(sys.argv[1:])

    greeting = open(args.greeting_filename, "r").read()
    print(f"message:\n{greeting[0:200]}...\n")
    df = pd.read_csv(args.input_filename[0])
    users = select_deleted_users(args, df)
    print(f"to {len(users)} {users=}")
    if not args.dry_run:
        message_users(args, users, greeting)
