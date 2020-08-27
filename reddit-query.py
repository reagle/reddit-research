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
indexing (often within 24 hours) and Reddit's current version.
"""

import argparse  # http://docs.python.org/dev/library/argparse.html
import datetime as dt
import logging
import sys
import pandas as pd
import time
from pathlib import Path, PurePath
from tqdm import tqdm

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
    for r in tqdm(results):
        info(f"{r['id']=} {r['author']=} {r['title']=}\n")
        created_utc = dt.datetime.fromtimestamp(r["created_utc"]).strftime(
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
                # PUSHSHIFT_API_URL + r["id"],
                # REDDIT_API_URL + r["id"],
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
            # "url_api_p",
            # "url_api_r",
        ],
    )
    return posts_df


def query_pushshift(
    name, limit, after, before, subreddit, query="", exclude="", score=">0",
):
    """Given search parameters, query pushshift and return JSON.

    after/before can be epoch, integer[s|m|h|d] or %Y%m%d"""

    # TODO
    # include: `selftext` parameter
    # exclude: `selftext:not` not supported by PSAW?

    pushshift_url = (
        f"https://api.pushshift.io/reddit/submission/search/"
        f"?limit={limit}&subreddit={subreddit}"
        f"&after={after}&before={before}&score={score}"
    )
    print(f"{pushshift_url=}")
    list_of_dicts = get_JSON(pushshift_url)["data"]
    return list_of_dicts


def collect_pushshift_results(
    name, limit, after, before, subreddit, query="", exclude="", score=">0",
):
    """Pushshift limited to 100 results, so need multiple queries to
    collect results in date range up to limit."""

    results = results_all = query_pushshift(
        name, limit, after, before, subreddit, query, exclude, score
    )
    while len(results) != 0 and len(results_all) < limit:
        time.sleep(1)
        after_new = results[-1]["created_utc"]  # + 1?
        after_new_human = time.strftime(
            "%a, %d %b %Y %H:%M:%S", time.gmtime(after_new)
        )
        info(f"{after_new_human=}")
        results = query_pushshift(
            name, limit, after_new, before, subreddit, query, exclude, score
        )
        results_all.extend(results)
        info(f"{len(results_all)=} {len(results)=}")

    return results_all[0:limit]


def export_df(name, df):

    df.to_csv(f"{name}.csv", encoding="utf-8-sig", index=False)
    print(f"saved dataframe of shape {df.shape} to '{name}.csv'")


def main(argv):
    """Process arguments"""
    arg_parser = argparse.ArgumentParser(
        description="Script for querying reddit APIs"
    )

    # optional arguments
    arg_parser.add_argument(
        "-a",
        "--after",
        type=str,
        default="2018-04-01",
        help="submissions after (default: %(default)s)",
    )
    arg_parser.add_argument(
        "-b",
        "--before",
        type=str,
        default="2018-04-30",
        help="submissions before (default: %(default)s)",
    )
    arg_parser.add_argument(
        "-k",
        "--keep",
        action="store_true",
        default=False,
        help="keep existing CSV files and don't overwrite (default: %(default)s)",
    )
    arg_parser.add_argument(
        "-l",
        "--limit",
        type=int,
        default=5,
        help="limit to (default: %(default)s) results",
    )
    arg_parser.add_argument(
        "-r",
        "--subreddit",
        type=str,
        default="AmItheAsshole",
        help="subreddit to query (default: %(default)s)",
    )
    arg_parser.add_argument(
        "-s",
        "--score",
        type=str,
        default=">0",
        help=r"score threshold '[<>]\d+]' (default: %(default)s)'",
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

    # synatactical tweaks to filename
    after = args.after.replace("-", "")
    before = args.before.replace("-", "")
    score = args.score
    if score[0] == ">":
        score = score[1:] + "+"
    elif score[0] == "<":
        score = score[1:] + "-"

    queries = (
        {
            "name": (
                f"reddit_{after}-{before}_{args.subreddit}"
                f"_s{score}_l{args.limit}"
            ),
            "limit": args.limit,
            "before": args.before,
            "after": args.after,
            "subreddit": args.subreddit,
            "score": args.score,
        },
    )

    for query in queries:
        print(f"{query=}")
        if args.keep and exists(f"{query['name']}.csv"):
            info(f"{query['name']}.csv already exists")
            continue
        else:
            ps_results = collect_pushshift_results(**query)
            posts_df = check_for_deleted(ps_results)
            export_df(query["name"], posts_df)
