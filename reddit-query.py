#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# DESCRIPTION
# (c) Copyright 2020 by Joseph Reagle
# Licensed under the GPLv3, see <http://www.gnu.org/licenses/gpl-3.0.html>
#

"""
What proportion of people on a subreddit delete their posts? This script pulls
from the Pushshift and Reddit APIs and generates a file with columns for
submissions' deletion status of author and message, at time of Pushshift's
indexing (often within 24 hours) and Reddit's current version.
"""

import argparse  # http://docs.python.org/dev/library/argparse.html
import datetime as dt
import logging
import random
import sys
import time
from pathlib import PurePath
from typing import Any, Tuple  # , Union

import numpy as np
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

# https://www.reddit.com/dev/api/
# https://github.com/pushshift/api
# import psaw  # Pushshift API https://github.com/dmarx/psaw no exclude:not

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


def is_throwaway(user_name):
    user_name = user_name.lower()
    if "throw" in user_name and "away" in user_name:
        return True
    else:
        return False


@cachier(stale_after=dt.timedelta(days=7))
def get_reddit_info(id, author_pushshift) -> Tuple[str, str, str]:
    """Given id, returns info from reddit."""

    if (not args.skip) or (
        args.throwaway_only and is_throwaway(author_pushshift)
    ):
        author_reddit = "[deleted]"
        is_deleted = "False"
        is_removed = "False"

        submission = REDDIT.submission(id=id)
        author_reddit = (
            "[deleted]" if not submission.author else submission.author
        )
        debug(f"reddit found {author_pushshift=}")
        is_deleted = submission.selftext == "[deleted]"
        is_removed = submission.selftext == "[removed]"
    else:
        debug(f"reddit skipped {author_pushshift=}")
        author_reddit = "NA"
        is_deleted = "NA"
        is_removed = "NA"

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
        created_utc = dt.datetime.fromtimestamp(pr["created_utc"]).strftime(
            "%Y%m%d %H:%M:%S"
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


@cachier(stale_after=dt.timedelta(days=7))
def query_pushshift(
    name,
    limit,
    after,
    before,
    subreddit,
    query="",
    num_comments=">0",
) -> Any:
    """Given search parameters, query pushshift and return JSON."""

    # https://github.com/pushshift/api

    RATE_LIMIT_SLEEP = 2
    time.sleep(RATE_LIMIT_SLEEP)

    if isinstance(after, str):
        after_human = after
    else:
        after_human = time.strftime("%Y%m%d %H:%M:%S", time.gmtime(after))
    if isinstance(before, str):
        before_human = before
    else:
        before_human = time.strftime("%Y%m%d %H:%M:%S", time.gmtime(before))
    critical(f"******* between {after_human} and {before_human}")

    optional_params = ""
    if after:
        optional_params += f"&after={after}"
    if before:
        optional_params += f"&before={before}"
    if num_comments:
        optional_params += f"&num_comments={num_comments}"
    if not args.moderated_include:
        optional_params += f"&selftext:not=[removed]"

    pushshift_url = (
        f"https://api.pushshift.io/reddit/submission/search/"
        f"?limit={limit}&subreddit={subreddit}{optional_params}"
    )
    print(f"{pushshift_url=}")
    json = get_JSON(pushshift_url)["data"]
    return json


def ordered_firsts_sample(items, limit) -> list:
    """Lfirsts in ple from items with order preserved."""

    info(f"{len(items)=}")
    info(f"{limit=}")
    sampled_index = np.linspace(0, len(items) - 1, limit).astype(int).tolist()
    info(f"{sampled_index=}")
    sampled_items = [items[token] for token in sampled_index]
    return sampled_items


def ordered_random_sample(items, limit) -> list:
    """Random sample from items with order preserved."""

    index = range(len(items))
    sampled_index = sorted(random.sample(index, limit))
    info(f"{sampled_index=}")
    sampled_items = [items[token] for token in sampled_index]
    return sampled_items


def collect_pushshift_results(
    name,
    limit,
    after,
    before,
    subreddit,
    query="",
    num_comments=">0",
) -> Any:
    """Pushshift limited to 100 results, so need multiple queries to
    collect results in date range up to or sampled from limit."""

    query_iteration = 1
    results = results_all = query_pushshift(
        name, limit, after, before, subreddit, query, num_comments
    )
    if args.sample:  # collect whole range and then sample to limit
        while len(results) != 0:
            critical(f"{query_iteration=}")
            query_iteration += 1
            after_new = results[-1]["created_utc"]  # + 1?
            results = query_pushshift(
                name, limit, after_new, before, subreddit, query, num_comments
            )
            results_all.extend(results)
        print(f"pushshift returned {len(results_all)} total")
        results_all = ordered_firsts_sample(results_all, limit)
        print(
            f"returning {len(results_all)} posts from random sample in range\n"
        )
    else:  # collect only firsts up to limit
        while len(results) != 0 and len(results_all) < limit:
            critical(f"{query_iteration=}")
            query_iteration += 1
            after_new = results[-1]["created_utc"]  # + 1?
            results = query_pushshift(
                name, limit, after_new, before, subreddit, query, num_comments
            )
            results_all.extend(results)
        results_all = results_all[0:limit]
        print(f"returning {len(results_all)} (first) posts in range\n")

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
        "-m",
        "--moderated_include",
        action="store_true",
        default=False,
        help=(
            "include moderated ['removed'] submissions "
            "(default: %(default)s)"
        ),
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
        help="throwaways checked; otherwise pushshift only "
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

    # mostly yntactical tweaks to filename
    if args.after and args.before:
        date = f"{args.after.replace('-','')}-{args.before.replace('-','')}"
    elif args.after:
        date = f"{args.after.replace('-','')}-NOW"  # TODO: make with {NOW}
    elif args.before:
        date = f"THEN-{args.before.replace('-','')}"  # TODO: make with {NOW}
    if args.num_comments:
        num_comments = args.num_comments
        if num_comments[0] == ">":
            num_comments = num_comments[1:] + "+"
        elif num_comments[0] == "<":
            num_comments = num_comments[1:] + "-"
        num_comments = "n" + num_comments
    else:
        num_comments = "n_"
    if args.sample:
        sample = "_sampled"
    else:
        sample = ""
    if args.throwaway_only:
        args.skip = True
        throwaway = "throwaway"
    else:
        throwaway = ""

    queries = (
        {
            "name": (
                f"""reddit_{date}_{args.subreddit}_{num_comments}"""
                f"""_l{args.limit}{sample}_{throwaway}"""
                # f"""_l{args.limit}_n{number}{sample}_{throwaway}"""
            ),
            "limit": args.limit,
            "before": args.before,
            "after": args.after,
            "subreddit": args.subreddit,
            "num_comments": args.num_comments,
        },
    )

    for query in queries:
        print(f"{query=}")
        ps_results = collect_pushshift_results(**query)
        posts_df = construct_df(ps_results)
        export_df(query["name"], posts_df)
