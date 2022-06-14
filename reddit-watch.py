#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# DESCRIPTION
# This file is part of Reddit Tools
# <https://github.com/reagle/reddit/>
# (c) Copyright 2020-2022 by Joseph Reagle
# Licensed under the GPLv3, see <http://www.gnu.org/licenses/gpl-3.0.html>

"""
Watch the deletion and moderation status of message IDs stored in a dictionary.
"""


# import cachier
# import datetime as dt
import argparse  # http://docs.python.org/dev/library/argparse.html
import logging
import numpy as np
import pprint
import pandas as pd
import sys
import tqdm

from collections import defaultdict
from pathlib import PurePath

# from typing import Any, Counter, Tuple  # , Union

import pendulum  # https://pendulum.eustace.io/docs/

# https://github.com/pushshift/api
# https://www.reddit.com/dev/api/
import praw  # https://praw.readthedocs.io/en/latest

# from tqdm import tqdm  # progress bar https://github.com/tqdm/tqdm

# import reddit_sample as rs
# import web_utils
from web_api_tokens import (
    REDDIT_CLIENT_ID,
    REDDIT_CLIENT_SECRET,
    REDDIT_USER_AGENT,
)


NOW = pendulum.now("UTC")
NOW_STR = NOW.format("YYYYMMDD HH:MM:SS")
PUSHSHIFT_LIMIT = 100
REDDIT_LIMIT = 100
pp = pprint.PrettyPrinter(indent=4)


reddit = praw.Reddit(
    user_agent=REDDIT_USER_AGENT,
    client_id=REDDIT_CLIENT_ID,
    client_secret=REDDIT_CLIENT_SECRET,
    ratelimit_seconds=600,
)

exception = logging.exception
critical = logging.critical
error = logging.error
warning = logging.warning
info = logging.info
debug = logging.debug


def main(argv) -> argparse.Namespace:
    """Process arguments"""
    arg_parser = argparse.ArgumentParser(
        description="Script for querying reddit APIs"
    )

    # non-positional arguments
    arg_parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="list greeting and users but don't message",
    )
    arg_parser.add_argument(
        "--start",
        action="store_true",
        default=False,
        help="throwaways checked on Reddit; otherwise Pushshift only "
        "(default: %(default)s)",
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


def start_watch(in_fn: str, watch_fn: str) -> None:
    """Start a new watcher CSV"""

    in_df = pd.read_csv(in_fn, encoding="utf-8-sig")
    print(f"read dataframe of shape {in_df.shape} from '{in_fn}'")
    row_dict = defaultdict(list)
    for _, row in in_df.iterrows():
        row_dict["id"].append(row["id"])
        row_dict["subreddit"].append(row["subreddit"])
        row_dict["author"].append(row["author_p"])
        row_dict["del_author_p"].append(row["del_author_p"])
        row_dict["created_utc"].append(row["created_utc"])
        row_dict["del_author_r"].append(row["del_author_r"])
        row_dict["del_author_r_changed"].append("NA")
        row_dict["del_text_r"].append(row["del_text_r"])
        row_dict["del_text_r_changed"].append("NA")
        row_dict["rem_text_r"].append(row["rem_text_r"])
        row_dict["rem_text_r_changed"].append("NA")
    watch_df = pd.DataFrame.from_dict(row_dict)
    watch_df.to_csv(watch_fn, index=True, encoding="utf-8-sig")


def prefetch_reddit_posts(ids_req: list[str]) -> dict:
    """Use praw's info() method to grab reddit info all at once."""

    submissions_dict = {}
    # temporarily limit to first 10 ids
    t3_ids = [i if i.startswith("t3_") else f"t3_{i}" for i in ids_req]
    print("fetching...")
    submissions = reddit.info(fullnames=t3_ids)
    for count, submission in tqdm.tqdm(enumerate(submissions)):
        # print(f"{submission.id=} {submission.author=}")
        submissions_dict[submission.id] = submission
    return submissions_dict


def update_watch(watched_fn: str) -> None:
    """Process a CSV, checking to see if values have changed and
    timestamping if so."""

    watched_df = pd.read_csv(watched_fn, encoding="utf-8-sig")
    updated_df = watched_df.copy()
    watched_ids = watched_df["id"].tolist()
    submissions = prefetch_reddit_posts(watched_ids)
    for index, row in watched_df.iterrows():
        id = row["id"]
        info(f"{row['id']=}, {row['author']=}")
        if id in submissions:
            sub = submissions[id]  # fetch and update if True
            # breakpoint()
            if np.isnan(row["del_author_r_changed"]):
                if sub.author == "[deleted]":
                    print(f"{sub.author=} deleted {NOW_STR}!")
                    updated_df.at[index, "del_author_r"] = True
                    updated_df.at[index, "del_author_r_changed"] = NOW_STR
            if np.isnan(row["del_text_r_changed"]):
                if sub.selftext == "[deleted]":
                    print(f"{sub.selftext=} deleted {NOW_STR}!")
                    updated_df.at[index, "del_text_r"] = True
                    updated_df.at[index, "del_text_r_changed"] = NOW_STR
            if np.isnan(row["rem_text_r_changed"]):
                if sub.selftext == "[removed]":
                    print(f"{sub.selftext=} removed {NOW_STR}!")
                    updated_df.at[index, "rem_text_r"] = True
                    updated_df.at[index, "rem_text_r_changed"] = NOW_STR
    updated_df.to_csv(
        "updated-" + watched_fn, index=True, encoding="utf-8-sig"
    )


if __name__ == "__main__":
    args = main(sys.argv[1:])

    FILENAMES = [
        "reddit_20220614-20220615_Advice_l10000_n677.csv",
        "reddit_20220614-20220615_AmItheAsshole_l10000_n854.csv",
        "reddit_20220614-20220615_relationship_advice_l10000_n1399.csv",
    ]
    for in_file_name in FILENAMES:
        print(f"{in_file_name=}")
        watch_file_name = "watch-" + in_file_name
        if args.start:
            start_watch(in_file_name, watch_file_name)
        # No "else" because even start needs to set initial to values
        # to a zero offset
        update_watch(watch_file_name)
        # TODO archive old watch, and rename the latest
