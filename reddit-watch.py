#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# DESCRIPTION
# This file is part of Reddit Tools
# <https://github.com/reagle/reddit/>
# (c) Copyright 2020-2022 by Joseph Reagle
# Licensed under the GPLv3, see <http://www.gnu.org/licenses/gpl-3.0.html>

"""
Watch the deletion and moderation status of messages tracked in a CSV.
"""

# import cachier
# import datetime as dt
import argparse  # http://docs.python.org/dev/library/argparse.html
import configparser as cp
import logging
import os
import pprint
import sys
import zipfile  # https://docs.python.org/3/library/zipfile.html
from collections import defaultdict
from pathlib import PurePath

import pandas as pd
import pendulum  # https://pendulum.eustace.io/docs/
import praw  # https://praw.readthedocs.io/en/latest
import tqdm  # progress bar https://github.com/tqdm/tqdm

# import reddit_sample as rs
# import web_utils
from web_api_tokens import (
    REDDIT_CLIENT_ID,
    REDDIT_CLIENT_SECRET,
    REDDIT_USER_AGENT,
)

# from typing import Any, Counter, Tuple  # , Union


# https://github.com/pushshift/api
# https://www.reddit.com/dev/api/


DATA_DIR = "/Users/reagle/data/1work/2020/reddit-del"
INI_FN = f"{DATA_DIR}/watch-reddit.ini"
NOW = pendulum.now("UTC")
NOW_STR = NOW.format("YYYYMMDD HH:mm:ss")
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


def init_watch_pushshift(subreddit: str, hours: int) -> str:
    """
    Initiate watch of subreddit using Pushshift, create CSV, return filename.
    """

    from psaw import PushshiftAPI

    print(f"\nInitializing watch on {subreddit}")
    hours_ago = NOW.subtract(hours=hours)
    hours_ago_as_timestamp = hours_ago.int_timestamp
    print(f"fetching initial posts from {subreddit}")
    pushshift = PushshiftAPI()
    submissions = pushshift.search_submissions(
        after=hours_ago_as_timestamp,
        subreddit=subreddit,
        filter=["id", "subreddit", "author", "created_utc"],
    )

    submissions_d = defaultdict(list)
    for submission in submissions:
        created_utc_human = pendulum.from_timestamp(
            submission.created_utc
        ).format("YYYYMMDD HH:mm:ss")

        submissions_d["id"].append(submission.id)
        submissions_d["subreddit"].append(submission.subreddit)
        submissions_d["author"].append(submission.author)
        submissions_d["del_author_p"].append("FALSE")
        submissions_d["created_utc"].append(created_utc_human)
        submissions_d["found_utc"].append(NOW_STR)
        submissions_d["del_author_r"].append("FALSE")
        submissions_d["del_author_r_changed"].append("NA")
        submissions_d["del_text_r"].append("FALSE")
        submissions_d["del_text_r_changed"].append("NA")
        submissions_d["rem_text_r"].append("FALSE")
        submissions_d["rem_text_r_changed"].append("NA")
        submissions_d["removed_by_category_r"].append("FALSE")

    watch_fn = (
        f"{DATA_DIR}/watch-{subreddit}-{NOW.format('YYYYMMDD')}"
        f"_n{len(submissions_d['id'])}.csv"
    )
    watch_df = pd.DataFrame.from_dict(submissions_d)
    watch_df.to_csv(watch_fn, index=True, encoding="utf-8-sig", na_rep="NA")
    return watch_fn


def init_watch_reddit(subreddit: str, limit: int) -> str:
    """
    Initiate watch of subreddit using Pushshift, create CSV, return filename.
    Reddit can return a maximum of only 1000 previous and recent submissions.
    """

    submissions_d = defaultdict(list)
    print(f"fetching initial posts from {subreddit}")
    prog_bar = tqdm.tqdm(total=limit)  # /REDDIT_LIMIT
    for submission in reddit.subreddit(subreddit).new(limit=limit):
        created_utc_human = pendulum.from_timestamp(
            submission.created_utc
        ).format("YYYYMMDD HH:mm:ss")

        submissions_d["id"].append(submission.id)
        submissions_d["subreddit"].append(submission.subreddit)
        submissions_d["author"].append(submission.author)
        submissions_d["del_author_p"].append("FALSE")
        submissions_d["created_utc"].append(created_utc_human)
        submissions_d["found_utc"].append(NOW_STR)
        submissions_d["del_author_r"].append("FALSE")
        submissions_d["del_author_r_changed"].append("NA")
        submissions_d["del_text_r"].append("FALSE")
        submissions_d["del_text_r_changed"].append("NA")
        submissions_d["rem_text_r"].append("FALSE")
        submissions_d["rem_text_r_changed"].append("NA")
        submissions_d["removed_by_category_r"].append("FALSE")
        prog_bar.update(1)
    prog_bar.close()
    watch_fn = (
        f"{DATA_DIR}/watch-{subreddit}-{NOW.format('YYYYMMDD')}"
        f"_n{len(submissions_d['id'])}.csv"
    )
    watch_df = pd.DataFrame.from_dict(submissions_d)
    watch_df.to_csv(watch_fn, index=True, encoding="utf-8-sig", na_rep="NA")
    return watch_fn


def prefetch_reddit_posts(ids_req: list[str]) -> dict:
    """Use praw's info() method to grab reddit info all at once."""

    submissions_dict = {}
    t3_ids = [i if i.startswith("t3_") else f"t3_{i}" for i in ids_req]
    print(f"prefetching {len(t3_ids)} ids...")
    prog_bar = tqdm.tqdm(total=len(t3_ids))
    for submission in reddit.info(fullnames=t3_ids):
        # print(f"{submission.id=} {submission.author=}")
        submissions_dict[submission.id] = submission
        prog_bar.update(1)
    prog_bar.close()
    return submissions_dict


def has_changed(a: str, b: str) -> bool:
    return a != b


def update_watch(watched_fn: str) -> str:
    """Process a CSV, checking to see if values have changed and
    timestamping if so."""

    print(f"Updating {watched_fn=}")
    assert os.path.exists(watched_fn)
    watched_df = pd.read_csv(watched_fn, encoding="utf-8-sig", index_col=0)
    updated_df = watched_df.copy()
    watched_ids = watched_df["id"].tolist()
    submissions = prefetch_reddit_posts(watched_ids)
    for index, row in watched_df.iterrows():
        id = row["id"]
        info(f"{row['id']=}, {row['author']=}")
        if id in submissions:
            # Different removed_by_category statuses:
            # https://www.reddit.com/r/redditdev/comments/kypjmk/check_if_submission_has_been_removed_by_a_mod/
            sub = submissions[id]  # fetch and update if True
            # author deletion
            if pd.isna(row["del_author_r_changed"]):
                # PRAW is now returning None, so test for that too
                # https://www.reddit.com/r/redditdev/comments/vhayaw/why_is_praw_returning_author_is_none_when_the/
                if sub.author == "[deleted]" or sub.author is None:
                    print(f"{sub.id=} author deleted {NOW_STR}")
                    updated_df.at[index, "del_author_r"] = True
                    updated_df.at[index, "del_author_r_changed"] = NOW_STR
            # message deletion
            if pd.isna(row["del_text_r_changed"]):
                if sub.selftext == "[deleted]":
                    print(f"{sub.id=} message deleted {NOW_STR}")
                    updated_df.at[index, "del_text_r"] = True
                    updated_df.at[index, "del_text_r_changed"] = NOW_STR
            # message removal (and possible deletion via removed_by_category):
            if sub.selftext == "[removed]":
                category_new = sub.removed_by_category
                category_old = row["removed_by_category_r"]
                if category_new != category_old:
                    # if not previously removed, update removal info
                    if pd.isna(row["rem_text_r_changed"]):
                        print(f"{sub.id=} removed {NOW_STR}")
                        updated_df.at[index, "rem_text_r"] = True
                        updated_df.at[index, "rem_text_r_changed"] = NOW_STR
                        updated_df.at[
                            index, "removed_by_category_r"
                        ] = category_new
                    # if status changed to delete, even if previously removed,
                    # update that as well
                    if category_new == "deleted":
                        print(f"  changed to deleted!")
                        updated_df.at[index, "del_text_r"] = True
                        updated_df.at[index, "del_text_r_changed"] = NOW_STR
                        updated_df.at[
                            index, "removed_by_category_r"
                        ] = category_new
                    # I'm ignoring other (if they exist) status changes
                    # (e.g., moderator modding their self with "author"?)

    head, tail = os.path.split(watched_fn)
    updated_fn = f"{head}/updated-{tail}"
    updated_df.to_csv(
        updated_fn, index=True, encoding="utf-8-sig", na_rep="NA"
    )
    return updated_fn


def rotate_archive_fns(updated_fn: str) -> None:

    print(f"Rotating and archiving {updated_fn=}")
    if not os.path.exists(updated_fn):
        raise RuntimeError(f"{os.path.exists(updated_fn)}")
    # print(f"{updated_fn=}")
    head, tail = os.path.split(updated_fn)
    os.chdir(head)
    print(f"{head=} {tail=}")
    bare_fn = tail.removeprefix("updated-").removesuffix(".csv")
    print(f"{bare_fn=}")
    stamped_fn = f"{bare_fn}-arch_{NOW.int_timestamp}.csv"
    print(f"{stamped_fn=}")
    zipped_fn = f"{bare_fn}-arch.zip"
    latest_fn = f"{bare_fn}.csv"
    print(f"{latest_fn=}")
    if [os.path.exists(fn) for fn in (latest_fn, updated_fn)]:
        print("rotating files")
        os.rename(latest_fn, stamped_fn)
        os.rename(updated_fn, latest_fn)
    else:
        raise RuntimeError(
            f"{os.path.exists(latest_fn)}" f"{os.path.exists(updated_fn)}"
        )
    if os.path.exists(zipped_fn):
        with zipfile.ZipFile(zipped_fn, mode="a") as archive:
            print(f"adding {stamped_fn=} to {zipped_fn}")
            archive.write(stamped_fn)
            # archive.printdir()
        print(f"deleting {stamped_fn=}")
        os.remove(stamped_fn)
    else:
        critical(f"can't append stamped, {zipped_fn} not found")


def init_archive(updated_fn: str) -> None:
    """
    Initialize the archive file with most recent version, to be
    added to with timestamped versions.
    """

    print(f"Initializing archive for {updated_fn=}")
    head, tail = os.path.split(updated_fn)
    bare_fn = tail.removeprefix("updated-").removesuffix(".csv")
    zipped_fn = f"{bare_fn}-arch.zip"
    print(f"  creating archive {zipped_fn=}")

    with zipfile.ZipFile(zipped_fn, mode="w") as archive:
        archive.write(updated_fn)


def main(argv) -> argparse.Namespace:
    """Process arguments"""
    arg_parser = argparse.ArgumentParser(
        description="Script for watching deletion/removal status"
        " of Reddit messages."
    )

    # non-positional arguments

    # optional arguments
    arg_parser.add_argument(
        "-i",
        "--init",
        type=str,
        default=False,
        help=f"""INITIALIZE `+` delimited subreddits to watch""",
    )
    arg_parser.add_argument(
        "--hours",
        type=int,
        default=24,
        help=f"""previous HOURS to fetch""",
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

    config = cp.ConfigParser(strict=False)

    if args.init:
        if not os.path.exists(INI_FN):
            with open(INI_FN, "w") as ini_fd:
                ini_fd.write("[watching]")
        config.read(INI_FN)
        for subreddit in args.init.split("+"):
            watched_fn = init_watch_pushshift(subreddit, args.hours)
            config.set("watching", f"{subreddit}{NOW_STR[0:8]}", watched_fn)
            updated_fn = update_watch(watched_fn)
            init_archive(updated_fn)
            rotate_archive_fns(updated_fn)
        with open(INI_FN, "w") as configfile:
            config.write(configfile)
    else:
        config.read(INI_FN)
        for watched, fn in config["watching"].items():
            updated_fn = update_watch(fn)
            rotate_archive_fns(updated_fn)
