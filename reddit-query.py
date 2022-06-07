#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# DESCRIPTION
# This file is part of Reddit Tools
# <https://github.com/reagle/reddit/>
# (c) Copyright 2020-2022 by Joseph Reagle
# Licensed under the GPLv3, see <http://www.gnu.org/licenses/gpl-3.0.html>

"""
What proportion of people on a subreddit delete their posts? This script pulls
from the Pushshift and Reddit APIs and generates a file with columns for
submissions' deletion status of author and message, at time of Pushshift's
indexing (often within 24 hours) and Reddit's current version.
"""

import argparse  # http://docs.python.org/dev/library/argparse.html
import datetime as dt
import logging
import pendulum  # https://pendulum.eustace.io/docs/

# import random
import sys

# import time
from pathlib import PurePath
from typing import Any, Tuple  # , Union

# import numpy as np
import pandas as pd
import praw  # https://praw.readthedocs.io/en/latest
from cachier import cachier  # https://github.com/shaypal5/cachier
from tqdm import tqdm  # progress bar https://github.com/tqdm/tqdm

from web_api_tokens import (
    REDDIT_CLIENT_ID,
    REDDIT_CLIENT_SECRET,
    REDDIT_USER_AGENT,
)

# https://github.com/reagle/thunderdell
from web_utils import get_JSON
from reddit_sample import get_offsets


# https://www.reddit.com/dev/api/
# https://github.com/pushshift/api
# import psaw  # Pushshift API https://github.com/dmarx/psaw no exclude:not

NOW = pendulum.now("UTC")
NOW_STR = NOW.format("YYYYMMDD")
PUSHSHIFT_LIMIT = 100


REDDIT = praw.Reddit(
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


def is_throwaway(user_name) -> bool:
    user_name = user_name.lower()
    if "throw" in user_name and "away" in user_name:
        return True
    else:
        return False


@cachier(pickle_reload=False)  #
def get_reddit_info(id, author_pushshift) -> Tuple[str, str, str]:
    """Given id, returns info from reddit."""

    author_reddit = "NA"
    is_deleted = "NA"
    is_removed = "NA"
    if args.skip:
        debug(f"reddit skipped because args.skip {author_pushshift=}")
    elif args.throwaway_only and not is_throwaway(author_pushshift):
        debug(
            f"reddit skipped because args.throwaway but not throwaway "
            f"{author_pushshift=}"
        )
    else:
        author_reddit = "[deleted]"
        is_deleted = "False"
        is_removed = "False"

        submission = REDDIT.submission(id=id)
        author_reddit = (
            "[deleted]" if not submission.author else submission.author
        )
        debug(f"reddit found {author_pushshift=}")
        debug(f"{submission=}")
        # https://www.reddit.com/r/pushshift/comments/v6vrmo/was_this_message_removed_or_deleted/
        is_deleted = submission.selftext == "[deleted]"
        is_removed = submission.selftext == "[removed]"

        if submission.selftext == "[removed]":
            is_removed = True
        if submission.selftext == "[deleted]":
            is_deleted = True
        if submission.removed_by_category == "deleted":
            is_deleted = True

    return author_reddit, is_deleted, is_removed


def construct_df(pushshift_results) -> Any:
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
    # PUSHSHIFT_API_URL = (
    #     "https://api.pushshift.io/reddit/submission/search?ids="
    # )
    # REDDIT_API_URL = "https://api.reddit.com/api/info/?id=t3_"

    results_checked = []
    for pr in tqdm(pushshift_results):
        debug(f"{pr['id']=} {pr['author']=} {pr['title']=}\n")
        created_utc = pendulum.from_timestamp(pr["created_utc"]).format(
            "YYYYMMDD HH:mm:ss"
        )
        elapsed_hours = round((pr["retrieved_on"] - pr["created_utc"]) / 3600)
        author_r, is_deleted_r, is_removed_r = get_reddit_info(
            pr["id"], pr["author"]
        )
        results_checked.append(
            (  # comments correspond to headings in dataframe below
                author_r,  # author_r(eddit)
                pr["author"],  # author_p(ushshift)
                pr["author"] == "[deleted]",  # del_author_p(ushshift)
                author_r == "[deleted]",  # del_author_r(eddit)
                pr["title"],  # title (pushshift)
                pr["id"],  # id (pushshift)
                created_utc,
                elapsed_hours,  # elapsed hours when pushshift indexed
                pr["score"],  # at time of ingest
                pr["num_comments"],  # updated as comments ingested?
                pr.get("selftext", "") == "[deleted]",  # del_text_p(ushshift)
                is_deleted_r,  # del_text_r(eddit)
                is_removed_r,  # rem_text_r(eddit)
                pr["url"],
                # PUSHSHIFT_API_URL + r["id"],
                # REDDIT_API_URL + r["id"],
            )
        )
    debug(results_checked)
    posts_df = pd.DataFrame(
        results_checked,
        columns=[
            "author_r",
            "author_p",
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


@cachier(pickle_reload=False)  # stale_after=dt.timedelta(days=7)
def query_pushshift(
    limit: int,
    after: dt.datetime,
    before: dt.datetime,
    subreddit: str,
    query: str = "",
    num_comments: str = ">0",
) -> Any:
    """Given search parameters, query pushshift and return JSON."""

    # https://github.com/pushshift/api

    # no need to pass different limit params beyond 100 (Pushshift's limit)
    # as it creates unnecessary keys in get_JSON cache
    if limit >= PUSHSHIFT_LIMIT:
        limit_param = f"limit={PUSHSHIFT_LIMIT}&"
    else:
        limit_param = f"limit={limit}&"

    after_human = after.format("YYYY-MM-DD HH:mm:ss")
    before_human = before.format("YYYY-MM-DD HH:mm:ss")
    critical(f"******* between {after_human} and {before_human}")
    after_timestamp = int(after.timestamp())
    before_timestamp = int(before.timestamp())
    critical(f"******* between {after_timestamp} and {before_timestamp}")

    optional_params = ""
    if after:
        optional_params += f"&after={after_timestamp}"
    if before:
        optional_params += f"&before={before_timestamp}"
    if num_comments:
        optional_params += f"&num_comments={num_comments}"

    pushshift_url = (
        f"https://api.pushshift.io/reddit/submission/search/"
        f"?{limit_param}subreddit={subreddit}{optional_params}"
    )
    print(f"{pushshift_url=}")
    json = get_JSON(pushshift_url)["data"]
    return json


def collect_pushshift_results(
    limit: int,
    after: dt.datetime,
    before: dt.datetime,
    subreddit: str,
    query: str = "",
    num_comments: str = ">0",
) -> Any:
    """Pushshift limited to PUSHSHIFT_LIMIT (100) results,
    so need multiple queries to collect results in date range up to
    or sampled at limit."""

    info(f"!! {after=}, {before=}")
    info(f"!! {after.timestamp()=}, {before.timestamp()=}")
    if args.sample:  # collect PUSHSHIFT_LIMIT at offsets

        # TODO/BUG: num_comments won't work with sampling estimates
        #   because they'll throw off the estimates

        query_iteration = 0
        offsets = get_offsets(after, before, limit, PUSHSHIFT_LIMIT)
        print(f"{offsets=}")
        results_all = []
        for after_offset in offsets:
            info(f"!! {after_offset=}, {before=}")
            query_iteration += 1
            results = query_pushshift(
                limit, after_offset, before, subreddit, query, num_comments
            )
            results_all.extend(results)

    else:  # collect only first message starting with after up to limit
        # I need an initial to see if there's anything in results
        query_iteration = 1
        results = results_all = query_pushshift(
            limit, after, before, subreddit, query, num_comments
        )
        while len(results) != 0 and len(results_all) < limit:
            critical(f"{query_iteration=}")
            query_iteration += 1
            after_new = pendulum.from_timestamp(results[-1]["created_utc"])
            results = query_pushshift(
                limit, after_new, before, subreddit, query, num_comments
            )
            results_all.extend(results)
        results_all = results_all[0:limit]
        print(f"returning {len(results_all)} (first) posts in range\n")

    info(f"{results_all=}")
    return results_all


def export_df(name, df) -> None:

    df.to_csv(f"{name}.csv", encoding="utf-8-sig", index=False)
    print(f"saved dataframe of shape {df.shape} to '{name}.csv'")


def main(argv) -> argparse.Namespace:
    """Process arguments"""
    arg_parser = argparse.ArgumentParser(
        description="Script for querying reddit APIs"
    )

    # optional arguments
    arg_parser.add_argument(
        "-a",
        "--after",
        type=str,
        default=False,
        help=f"""submissions after: epoch, integer[s|m|h|d], or Y-m-d"""
        """Using it with before starts in 1970!""",
    )
    arg_parser.add_argument(
        "-b",
        "--before",
        type=str,
        default=False,
        help="""submissions before: epoch, integer[s|m|h|d], or Y-m-d""",
    )
    # # TODO: add cache clearing mechanism
    # arg_parser.add_argument(
    #     "-c",
    #     "--clear_cache",
    #     type=bool,
    #     default=False,
    #     help="""clear web I/O cache (default: %(default)s).""",
    # )
    arg_parser.add_argument(
        "-l",
        "--limit",
        type=int,
        default=5,
        help="limit to (default: %(default)s) results ",
    )
    arg_parser.add_argument(
        "-n",
        "--num_comments",
        type=str,
        default=False,
        help="""number of comments threshold """
        r"""'[<>]\d+]' (default: %(default)s). """
        """Note: this is updated as Pushshift ingests, `score` is not.""",
    )
    arg_parser.add_argument(
        "-r",
        "--subreddit",
        type=str,
        default="AmItheAsshole",
        help="subreddit to query (default: %(default)s)",
    )
    arg_parser.add_argument(
        "--sample",
        action="store_true",
        default=False,
        help="""sample complete date range up to limit, rather than """
        """first submissions within limit (default: %(default)s)""",
    )
    arg_parser.add_argument(
        "--skip",
        action="store_true",
        default=False,
        help="skip all reddit queries; pushshift only "
        "(default: %(default)s)",
    )
    arg_parser.add_argument(
        "-t",
        "--throwaway-only",
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


if __name__ == "__main__":
    args = main(sys.argv[1:])

    # syntactical tweaks to filename
    if args.after and args.before:
        after = pendulum.parse(args.after)
        before = pendulum.parse(args.before)
        date = f"{after.format('YYYYMMDD')}-{before.format('YYYYMMDD')}"
    elif args.after:
        after = pendulum.parse(args.after)
        date = f"{after.format('YYYYMMDD')}-{NOW_STR}"
    elif args.before:
        raise RuntimeError("--before cannot be used with --after")
    if args.num_comments:
        num_comments = args.num_comments
        if num_comments[0] == ">":
            num_comments = num_comments[1:] + "+"
        elif num_comments[0] == "<":
            num_comments = num_comments[1:] + "-"
        num_comments = "_nc" + num_comments
    else:
        num_comments = ""
    if args.sample:
        sample = "_sampled"
    else:
        sample = ""
    if args.throwaway_only:
        throwaway = "_throwaway"
    else:
        throwaway = ""

    query = {
        "limit": args.limit,
        "before": before,
        "after": after,
        "subreddit": args.subreddit,
        "num_comments": args.num_comments,
    }
    print(f"{query=}")
    ps_results = collect_pushshift_results(**query)
    posts_df = construct_df(ps_results)
    number_results = len(posts_df)
    result_name = (
        f"""reddit_{date}_{args.subreddit}{num_comments}"""
        f"""_l{args.limit}_n{number_results}{sample}{throwaway}"""
    )
    export_df(result_name, posts_df)
