#!/usr/bin/env python3
"""Query Pushshift and Reddit data.

Pull from the Pushshift and Reddit APIs and generate a file with columns
for submissions' deletion status of author and message, at time of Pushshift's indexing
(often within 24 hours) and Reddit's current version. This permits one to answer the
question: What proportion of people on a subreddit delete their posts?
"""

__author__ = "Joseph Reagle"
__copyright__ = "Copyright (C) 2009-2023 Joseph Reagle"
__license__ = "GLPv3"
__version__ = "1.0"

import argparse  # http://docs.python.org/dev/library/argparse.html
import collections
import logging as log
import pathlib as pl
import shelve
import sys
import typing as typ

import pandas as pd
import pendulum  # https://pendulum.eustace.io/docs/
import praw  # type: ignore # https://praw.readthedocs.io/en/latest
import tqdm  # progress bar https://github.com/tqdm/tqdm

from reddit_research import reddit_sample as rs
from reddit_research import web_utils

# https://github.com/pushshift/api
# import psaw  # Pushshift API https://github.com/dmarx/psaw no exclude:not

NOW = pendulum.now("UTC")
NOW_STR = NOW.format("YYYYMMDD")
PUSHSHIFT_LIMIT = 100
REDDIT_LIMIT = 100

REDDIT = praw.Reddit(
    user_agent=web_utils.get_credential("REDDIT_USER_AGENT"),
    client_id=web_utils.get_credential("REDDIT_CLIENT_ID"),
    client_secret=web_utils.get_credential("REDDIT_CLIENT_SECRET"),
    username=web_utils.get_credential("REDDIT_USERNAME"),
    password=web_utils.get_credential("REDDIT_PASSWORD"),
    ratelimit_seconds=600,
)


# This is duplicated in reddit-query.py and reddit-message.py
def is_throwaway(user_name: str) -> bool:
    """Determine if a user name is a throwaway account."""
    name = user_name.lower()
    # "throwra" is common throwaway in (relationship) advice subreddits
    return ("throw" in name and "away" in name) or ("throwra" in name)


def prefetch_reddit_posts(ids_req: list[str]) -> shelve.Shelf[typ.Any]:
    """Use praw's info() method to pre-fetch and cache Reddit info."""
    # TODO if key already in shelf continue, otherwise grab
    # Break up into 100s
    shelf = shelve.open("shelf-reddit.dbm")
    ids_shelved = set(shelf.keys())
    ids_needed = set(ids_req) - ids_shelved
    t3_ids = [i if i.startswith("t3_") else f"t3_{i}" for i in ids_needed]
    submissions = REDDIT.info(fullnames=t3_ids)
    print("pre-fetch: storing in shelf")
    for submission in tqdm.tqdm(submissions, total=len(t3_ids)):
        # print(f"{count: <3} {submission.id} {submission.title}")
        shelf[submission.id] = submission
    return shelf


def get_reddit_info(
    args: argparse.Namespace,
    shelf: shelve.Shelf[typ.Any],
    id_: str,
    author_pushshift: str,
) -> tuple[str, bool, bool]:
    """Given id, returns info from reddit."""
    author_reddit = "NA"
    is_deleted = False
    is_removed = False
    if args.skip:
        log.debug(f"reddit skipped because args.skip {author_pushshift=}")
    elif args.throwaway_only and not is_throwaway(author_pushshift):
        log.debug(
            "reddit skipped because args.throwaway_only but not throwaway "
            + f"{author_pushshift=}"
        )
    else:
        author_reddit = "[deleted]"

        # submission = REDDIT.submission(id=id_)
        if id_ in shelf:
            submission = shelf[id_]
        else:
            # These instances are very rare 0.001%
            # https://www.reddit.com/r/pushshift/comments/vby7c2/rare_pushshift_has_a_submission_id_reddit_returns/icbbtkr/?context=3
            print(f"WARNING: {id_=} not in shelf")
            return "[deleted]", False, False
        author_reddit = "[deleted]" if not submission.author else submission.author
        log.debug(f"reddit found {author_pushshift=}")
        log.debug(f"{submission=}")
        # https://www.reddit.com/r/pushshift/comments/v6vrmo/was_this_message_removed_or_deleted/
        is_removed = submission.selftext == "[removed]"
        if (
            submission.selftext == "[deleted]"
            or submission.title == "[deleted by user]"
        ):
            is_deleted = True
        # when removed and then deleted, set deleted as well
        if submission.removed_by_category == "deleted":
            is_deleted = True

    return author_reddit, is_deleted, is_removed


def construct_df(args, pushshift_total: int, pushshift_results: list[dict]) -> typ.Any:
    """Given pushshift query results, return dataframe of info about submissions.

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

    results_row = []
    ids_counter = collections.Counter()

    ids_all = [message["id"] for message in pushshift_results]
    shelf = prefetch_reddit_posts(ids_all)
    for pr in tqdm.tqdm(pushshift_results, total=len(ids_all)):
        log.debug(f"{pr['id']=} {pr['author']=} {pr['title']=}\n")
        ids_counter[pr["id"]] += 1
        created_utc = pendulum.from_timestamp(pr["created_utc"]).format(
            "YYYYMMDD HH:mm:ss"
        )
        elapsed_hours = round((pr["retrieved_on"] - pr["created_utc"]) / 3600)
        author_r, is_deleted_r, is_removed_r = get_reddit_info(
            args, shelf, pr["id"], pr["author"]
        )
        results_row.append(
            (  # comments correspond to headings in dataframe below
                pr["subreddit"],
                pushshift_total,  # total_p: total range if sampling
                author_r,  # author_r(eddit)
                pr["author"],  # author_p(ushshift)
                pr["author"] == "[deleted]",  # del_author_p(ushshift)
                author_r == "[deleted]",  # del_author_r(eddit)
                pr["id"],  # id (pushshift)
                pr["title"],  # title (pushshift)
                created_utc,
                elapsed_hours,  # elapsed hours when pushshift indexed
                pr["score"],  # at time of ingest
                pr["num_comments"],  # updated as comments ingested
                pr.get("selftext", "") == "[deleted]",  # del_text_p(ushshift)
                is_deleted_r,  # del_text_r(eddit)
                is_removed_r,  # rem_text_r(eddit)
                # the following using
                pr["full_link"] != pr.get("url"),  # crosspost
                pr["full_link"],  # url
                # PUSHSHIFT_API_URL + r["id"],
                # REDDIT_API_URL + r["id"],
            )
        )
    log.debug(results_row)

    COLUMNS = (
        [
            "subreddit",
            "total_p",
            "author_r",
            "author_p",
            "del_author_p",  # on pushshift
            "del_author_r",  # on reddit
            "id",
            "title",
            "created_utc",
            "elapsed_hours",
            "score_p",
            "comments_num_p",
            "del_text_p",
            "del_text_r",
            "rem_text_r",
            "crosspost",
            "url",
            # "url_api_p",
            # "url_api_r",
        ],
    )
    posts_df = pd.DataFrame(results_row, columns=pd.Index(COLUMNS))
    ids_repeating = [m_id for m_id, count in ids_counter.items() if count > 1]
    if ids_repeating:
        print(f"WARNING: repeat IDs = {ids_repeating=}")
    return posts_df


def query_pushshift(
    limit: int,
    after: pendulum.DateTime,
    before: pendulum.DateTime,
    subreddit: str,
    query: str = "",
    comments_num: str = ">0",
) -> typ.Any:
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
    log.critical(f"******* between {after_human} and {before_human}")
    after_timestamp = after.int_timestamp
    before_timestamp = before.int_timestamp
    log.debug(f"******* between {after_timestamp} and {before_timestamp}")

    optional_params = ""
    if after:
        optional_params += f"&after={after_timestamp}"
    if before:
        optional_params += f"&before={before_timestamp}"
    if comments_num:
        # I prefer `comments_num`, but Reddit uses poorly
        # named `num_comments`
        optional_params += f"&num_comments={comments_num}"
    # this can be use to remove typ.any message with "removed"
    # see earlier commits for full functionality
    # optional_params += f"&selftext:not=[removed]"

    pushshift_url = (
        "https://api.pushshift.io/reddit/submission/search/"
        + f"?{limit_param}subreddit={subreddit}{optional_params}"
    )
    print(f"{pushshift_url=}")
    pushshift_data = web_utils.get_JSON(pushshift_url)
    if not isinstance(pushshift_data, dict):
        raise TypeError("Expected a dictionary from get_JSON")
    pushshift_data = pushshift_data["data"]
    if len(pushshift_data) != 100:
        print(f"short on some entries {len(pushshift_data)}")
        # breakpoint()
    return pushshift_data


def collect_pushshift_results(
    args: argparse.Namespace,
    limit: int,
    after: pendulum.DateTime,
    before: pendulum.DateTime,
    subreddit: str,
    query: str = "",
    comments_num: str = ">0",
) -> tuple[int, typ.Any]:
    """Breakup queries by PUSHSHIFT_LIMIT.

    Pushshift limited to PUSHSHIFT_LIMIT (100) results,
    so need multiple queries to collect results in date range up to
    or sampled at limit.
    """
    log.info(f"{after=}, {before=}")
    log.info(f"{after.timestamp()=}, {before.timestamp()=}")
    if args.sample:  # collect PUSHSHIFT_LIMIT at offsets
        # TODO/BUG: comments_num won't work with sampling estimates
        #   because they'll throw off the estimates

        results_total = rs.get_pushshift_total(subreddit, after, before)
        offsets = rs.get_offsets(subreddit, after, before, limit, PUSHSHIFT_LIMIT)
        log.info(f"{offsets=}")
        results_found = []
        for query_iteration, after_offset in enumerate(offsets):
            log.info(f"{after_offset=}, {before=}")
            log.critical(f"{query_iteration}")
            results = query_pushshift(
                limit, after_offset, before, subreddit, query, comments_num
            )
            results_found.extend(results)

    else:  # collect only first message starting with after up to limit
        # I need an initial to see if there's anything in results
        results_total = rs.get_pushshift_total(subreddit, after, before)
        query_iteration = 1
        results = results_found = query_pushshift(
            limit, after, before, subreddit, query, comments_num
        )
        while len(results) != 0 and len(results_found) < limit:
            log.critical(f"{query_iteration=}")
            query_iteration += 1
            after_new = pendulum.from_timestamp(results[-1]["created_utc"])
            results = query_pushshift(
                limit, after_new, before, subreddit, query, comments_num
            )
            results_found.extend(results)
        results_found = results_found[0:limit]
        print(f"returning {len(results_found)} (first) posts in range\n")

    log.info(f"{results_total=}")
    log.info(f"{results_found=}")
    return results_total, results_found


def export_df(name, df) -> None:
    """Export dataframe to CSV."""
    df.to_csv(f"{name}.csv", encoding="utf-8-sig", index=False)
    print(f"saved dataframe of shape {df.shape} to '{name}.csv'")


def process_args(argv) -> argparse.Namespace:
    """Process arguments."""
    arg_parser = argparse.ArgumentParser(description="Query Pushshift and Reddit APIs.")

    # optional arguments
    arg_parser.add_argument(
        "-a",
        "--after",
        type=str,
        default=False,
        help="""submissions after: Y-m-d (any pendulum parsable)."""
        + """ Using it without before starts in 1970!""",
    )
    arg_parser.add_argument(
        "-b",
        "--before",
        type=str,
        default=False,
        help="""submissions before: Y-m-d (any pendulum parsable)."""
        + """ Using it without before starts in 1970!""",
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
        "-c",
        "--comments_num",
        type=str,
        default=False,
        help="""number of comments threshold """
        + r"""'[<>]\d+]' (default: %(default)s). """
        + """Note: this is updated as Pushshift ingests, `score` is not.""",
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
        + """first submissions within limit""",
    )
    arg_parser.add_argument(
        "--skip",
        action="store_true",
        default=False,
        help="skip all Reddit fetches; pushshift only",
    )
    arg_parser.add_argument(
        "-t",
        "--throwaway-only",
        action="store_true",
        default=False,
        help=(
            """only throwaway accounts ('throw' and 'away') get """
            + """ fetched from Reddit"""
        ),
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
    arg_parser.add_argument("--version", action="version", version="0.4")
    args = arg_parser.parse_args(argv)

    log_level = (log.CRITICAL) - (args.verbose * 10)
    LOG_FORMAT = "%(levelname).4s %(funcName).10s:%(lineno)-4d| %(message)s"
    if args.log_to_file:
        print("logging to file")
        log.basicConfig(
            filename=f"{pl.PurePath(__file__).name!s}.log",
            filemode="w",
            level=log_level,
            format=LOG_FORMAT,
        )
    else:
        log.basicConfig(level=log_level, format=LOG_FORMAT)

    return args


def main() -> None:
    """Set up arguments and call functions."""
    # syntactical tweaks to filename
    after = before = date_str = None
    args = process_args(sys.argv[1:])
    if args.after and args.before:
        after: pendulum.DateTime = pendulum.parse(args.after)
        before: pendulum.DateTime = pendulum.parse(args.before)
        date_str = f"{after.format('YYYYMMDD')}-{before.format('YYYYMMDD')}"
    elif args.after:
        after = pendulum.parse(args.after)
        date_str = f"{after.format('YYYYMMDD')}-{NOW_STR}"
    elif args.before:
        raise ValueError("--before cannot be used without --after")
    else:
        raise ValueError("Invalid date range specified")

    if args.comments_num:
        comments_num = args.comments_num
        if comments_num[0] == ">":
            comments_num = comments_num[1:] + "+"
        elif comments_num[0] == "<":
            comments_num = comments_num[1:] + "-"
        comments_num = "_c" + comments_num
    else:
        comments_num = ""
    sample = "_sampled" if args.sample else ""
    throwaway = "_throwaway" if args.throwaway_only else ""

    query = {
        "limit": args.limit,
        "before": before,
        "after": after,
        "subreddit": args.subreddit,
        "comments_num": args.comments_num,
    }
    print(f"{query=}")
    ps_total, ps_results = collect_pushshift_results(args, **query)
    posts_df = construct_df(args, ps_total, ps_results)
    number_results = len(posts_df)
    result_name = (
        f"""reddit_{date_str}_{args.subreddit}{comments_num}"""
        + f"""_l{args.limit}_n{number_results}{sample}{throwaway}"""
    )
    export_df(result_name, posts_df)


if __name__ == "__main__":
    main()
