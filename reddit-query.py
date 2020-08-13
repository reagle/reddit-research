#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# DESCRIPTION
# (c) Copyright 2020 by Joseph Reagle
# Licensed under the GPLv3, see <http://www.gnu.org/licenses/gpl-3.0.html>
#

"""
What proportion of people on a subreddit delete their posts? This script pulls
from the Pushshift and Reddit APIs and generates a file with columns for
submissions deletion status of author and message, at time of Pushshift's
indexing (often within 24 hours) and Reddit'S current version.
"""

import argparse  # http://docs.python.org/dev/library/argparse.html
import datetime as dt
import logging
import sys
import pandas as pd
from pathlib import Path, PurePath

# https://www.reddit.com/dev/api/
import praw  # https://praw.readthedocs.io/en/latest

from web_api_tokens import (
    REDDIT_CLIENT_ID,
    REDDIT_CLIENT_SECRET,
    REDDIT_USER_AGENT,
)

# https://github.com/reagle/thunderdell
from web_utils import get_JSON

# https://github.com/pushshift/api
# import psaw  # https://github.com/dmarx/psaw no exclude:not


REDDIT = praw.Reddit(
    user_agent=REDDIT_USER_AGENT,
    client_id=REDDIT_CLIENT_ID,
    client_secret=REDDIT_CLIENT_SECRET,
)

exception = logging.exception
critical = logging.critical
error = logging.error
warning = logging.warning
info = logging.info
debug = logging.debug


def get_reddit_info(id):
    """Given id, returns info from reddit."""

    author = "[deleted]"
    is_deleted = False
    is_removed = False

    submission = REDDIT.submission(id=id)
    author = "[deleted]" if not submission.author else submission.author
    debug(f"{author=}")
    is_deleted = submission.selftext == "[deleted]"
    is_removed = submission.selftext == "[removed]"
    return author, is_deleted, is_removed


def check_for_deleted(results):
    """Given pushshift query results, return dataframe of info about
    submissions.
    """
    """
    https://github.com/pushshift/api
    https://github.com/dmarx/psaw

    https://www.reddit.com/dev/api/
    https://praw.readthedocs.io/en/latest
    """

    # Use these for manual confirmation of results
    PUSHSHIFT_API_URL = (
        "https://api.pushshift.io/reddit/submission/search?ids="
    )
    REDDIT_API_URL = "https://api.reddit.com/api/info/?id=t3_"

    results_checked = []
    for r in results:
        info(f"{r['id']=} {r['author']=} {r['title']=}\n")
        created_utc = dt.date.fromtimestamp(r["created_utc"]).strftime(
            "%Y%m%d %H:%M:%S"
        )
        elapsed_hours = round((r["retrieved_on"] - r["created_utc"]) / 3600)
        author, is_deleted, is_removed = get_reddit_info(r["id"])
        results_checked.append(
            (
                author,  # author_r(eddit)
                r["author"] == "[deleted]",  # del_author_p(ushshift)
                author == "[deleted]",  # del_author_r(eddit)
                r["title"],  # title (pushshift)
                r["id"],  # id (pushshift)
                created_utc,
                elapsed_hours,  # elapsed hours when pushshift indexed
                r["score"],
                r["num_comments"],
                r.get("selftext", "") == "[deleted]",  # del_text_p(ushshift)
                is_deleted,  # del_text_r(eddit)
                is_removed,  # rem_text_r(eddit)
                r["url"],
                PUSHSHIFT_API_URL + r["id"],
                REDDIT_API_URL + r["id"],
            )
        )
    debug(results_checked)
    posts_df = pd.DataFrame(
        results_checked,
        columns=[
            "author_r",
            "del_author_p",  # on pushshift
            "del_author_r",  # on reddit
            "title",
            "id",
            "created_utc",
            "elapsed_hours",
            "score_p",
            "num_comments_p",
            "del_text_p",
            "del_text_r",
            "rem_text_r",
            "url",
            "url_api_p",
            "url_api_r",
        ],
    )
    return posts_df


def query_pushshift(
    name, limit, after, before, subreddit, query="", exclude="", score=">0",
):
    """given search parameters, query pushshift and return JSON"""

    # TODO
    # include: `selftext` parameter
    # exclude: `selftext:not` not supported by PSAW?

    pushshift_url = (
        f"https://api.pushshift.io/reddit/submission/search/"
        f"?limit={limit}&subreddit={subreddit}"
        f"&after={after}&before={before}&score={score}"
    )
    info(f"{len(pushshift_url)=}")
    data_total = get_JSON(pushshift_url)["data"]
    return data_total


def export_df(name, df):

    df.to_csv(f"{name}.csv", encoding="utf-8-sig")


def main(argv):
    """Process arguments"""
    arg_parser = argparse.ArgumentParser(description="TBD")

    # positional arguments
    arg_parser.add_argument("files", nargs="?", metavar="FILE")
    # optional arguments
    arg_parser.add_argument(
        "-k",
        "--keep",
        action="store_true",
        default=False,
        help="keep existing CSV files -- when adding a new query",
    )
    arg_parser.add_argument(
        "-l",
        "--limit",
        type=int,
        default=5,
        help="limit query results to N (default: %(default)s)",
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
        help="Increase verbosity (specify multiple times for more)",
    )
    arg_parser.add_argument("--version", action="version", version="TBD")
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

    queries = (
        {
            "name": "reddit-2018-AItA",
            "limit": args.limit,
            "after": "2018-04-01",
            "before": "2018-04-30",
            "subreddit": "AmItheAsshole",
        },
        {
            "name": "reddit-2018-AItA-100",
            "limit": args.limit,
            "after": "2018-04-01",
            "before": "2018-04-30",
            "subreddit": "AmItheAsshole",
            "score": ">100",
        },
    )

    for query in queries:
        print(f"{query=}")
        if args.keep and exists(f"{query['name']}.csv"):
            info(f"{query['name']}.csv already exists")
            continue
        else:
            ps_results = query_pushshift(**query)
            posts_df = check_for_deleted(ps_results)
            export_df(query["name"], posts_df)
