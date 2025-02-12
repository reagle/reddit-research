#!/usr/bin/env python3
"""Watch the deletion and moderation status of messages tracked in a CSV.

You must initialize the subreddit you wish to follow first.
"""

__author__ = "Joseph Reagle"
__copyright__ = "Copyright (C) 2022-2023 Joseph Reagle"
__license__ = "GLPv3"
__version__ = "1.0"

import argparse  # http://docs.python.org/dev/library/argparse.html
import collections
import configparser as cp
import logging as log
import pprint
import sys
import zipfile  # https://docs.python.org/3/library/zipfile.html
from pathlib import Path

import pandas as pd
import pendulum  # https://pendulum.eustace.io/docs/
import praw  # type: ignore # https://praw.readthedocs.io/en/latest
import tqdm  # progress bar https://github.com/tqdm/tqdm

from reddit_research import web_utils

HOMEDIR = Path.home()
DATA_DIR = HOMEDIR / "data/1work/2020/reddit-del/"
INI_FN = DATA_DIR / "watch-REDDIT.ini"
NOW = pendulum.now("UTC")
NOW_STR = NOW.format("YYYYMMDD HH:mm:ss")
PUSHSHIFT_LIMIT = 100
REDDIT_LIMIT = 100
pp = pprint.PrettyPrinter(indent=4)

REDDIT = praw.Reddit(
    user_agent=web_utils.get_credential("REDDIT_USER_AGENT"),
    client_id=web_utils.get_credential("REDDIT_CLIENT_ID"),
    client_secret=web_utils.get_credential("REDDIT_CLIENT_SECRET"),
    username=web_utils.get_credential("REDDIT_USERNAME"),
    password=web_utils.get_credential("REDDIT_PASSWORD"),
    ratelimit_seconds=600,
)


def init_watch_pushshift(subreddit: str, hours: int) -> Path:
    """Initiate watch of subreddit using Pushshift, create CSV, return filename."""
    import psaw

    print(f"\nInitializing watch on {subreddit}")
    hours_ago = NOW.subtract(hours=hours)
    hours_ago_as_timestamp = hours_ago.int_timestamp
    print(f"fetching initial posts from {subreddit}")
    pushshift = psaw.PushshiftAPI()
    submissions = pushshift.search_submissions(
        after=hours_ago_as_timestamp,
        subreddit=subreddit,
        filter=["id", "subreddit", "author", "created_utc"],
    )

    submissions_d = collections.defaultdict(list)
    for submission in submissions:
        created_utc_human = pendulum.from_timestamp(submission.created_utc).format(
            "YYYYMMDD HH:mm:ss"
        )

        submissions_d["id"].append(submission.id)
        submissions_d["subreddit"].append(submission.subreddit)
        submissions_d["author_p"].append(submission.author)
        submissions_d["del_author_p"].append("FALSE")
        submissions_d["created_utc"].append(created_utc_human)
        submissions_d["found_utc"].append(NOW_STR)
        submissions_d["checked_utc"].append(NOW_STR)
        submissions_d["del_author_r"].append("FALSE")
        submissions_d["del_author_r_utc"].append("NA")
        submissions_d["del_text_r"].append("FALSE")
        submissions_d["del_text_r_utc"].append("NA")
        submissions_d["rem_text_r"].append("FALSE")
        submissions_d["rem_text_r_utc"].append("NA")
        submissions_d["removed_by_category_r"].append("FALSE")

    watch_fn = (
        DATA_DIR
        / f"watch-{subreddit}-{NOW.format('YYYYMMDD')}_n{len(submissions_d['id'])}.csv"
    )
    watch_df = pd.DataFrame.from_dict(submissions_d)
    watch_df.to_csv(watch_fn, index=True, encoding="utf-8-sig", na_rep="NA")
    return watch_fn


def init_watch_reddit(subreddit: str, limit: int) -> Path:
    """Initiate watch of subreddit using Reddit, create CSV, return filename.

    Reddit can return a maximum of only 1000 recent and previous submissions.
    Even when Pushshift is down.

    DEPRECATED as Pushshift should have ids which Reddit won't.
    """
    submissions_d = collections.defaultdict(list)
    print(f"fetching initial posts from {subreddit}")
    prog_bar = tqdm.tqdm(total=limit)
    for submission in REDDIT.subreddit(subreddit).new(limit=limit):
        created_utc_human = pendulum.from_timestamp(submission.created_utc).format(
            "YYYYMMDD HH:mm:ss"
        )

        submissions_d["id"].append(submission.id)
        submissions_d["subreddit"].append(submission.subreddit)
        submissions_d["author_p"].append(submission.author)
        submissions_d["del_author_p"].append("FALSE")
        submissions_d["created_utc"].append(created_utc_human)
        submissions_d["found_utc"].append(NOW_STR)
        submissions_d["checked_utc"].append(NOW_STR)
        submissions_d["del_author_r"].append("FALSE")
        submissions_d["del_author_r_utc"].append("NA")
        submissions_d["del_text_r"].append("FALSE")
        submissions_d["del_text_r_utc"].append("NA")
        submissions_d["rem_text_r"].append("FALSE")
        submissions_d["rem_text_r_utc"].append("NA")
        submissions_d["removed_by_category_r"].append("FALSE")
        prog_bar.update(1)
    prog_bar.close()
    watch_fn = (
        DATA_DIR
        / f"watch-{subreddit}-{NOW.format('YYYYMMDD')}_n{len(submissions_d['id'])}.csv"
    )
    watch_df = pd.DataFrame.from_dict(submissions_d)
    watch_df.to_csv(watch_fn, index=True, encoding="utf-8-sig", na_rep="NA")
    return watch_fn


def prefetch_reddit_posts(ids_req: tuple[str]) -> dict:
    """Use PRAW's info() method to grab Reddit info all at once."""
    submissions_dict = {}
    t3_ids = [i if i.startswith("t3_") else f"t3_{i}" for i in ids_req]
    print(f"prefetching {len(t3_ids)} ids...")
    prog_bar = tqdm.tqdm(total=len(t3_ids))
    for submission in REDDIT.info(fullnames=t3_ids):
        submissions_dict[submission.id] = submission
        prog_bar.update(1)
    prog_bar.close()
    return submissions_dict


def update_watch(watched_fn: Path) -> Path:
    """Process a CSV, checking to see if values have changed and timestamping if so."""
    print(f"Updating {watched_fn=}")
    assert watched_fn.exists()
    watched_df = pd.read_csv(watched_fn, encoding="utf-8-sig", index_col=0)
    updated_df = watched_df.copy()
    watched_ids = tuple(watched_df["id"].tolist())
    submissions = prefetch_reddit_posts(watched_ids)
    for index, row in watched_df.iterrows():
        id_ = row["id"]
        if id_ not in submissions:
            print(f"{id_=} no longer in submissions, continuing")
            continue
        log.info(f"{row['id']=}, {row['author_p']=}")
        sub = submissions[id_]
        updated_df.at[index, "checked_utc"] = NOW_STR
        if pd.isna(row["del_author_r_utc"]):
            if sub.author == "[deleted]" or sub.author is None:
                print(f"{sub.id=} author deleted {NOW_STR}")
                updated_df.at[index, "del_author_r"] = True
                updated_df.at[index, "del_author_r_utc"] = NOW_STR
        if pd.isna(row["del_text_r_utc"]):
            if sub.selftext == "[deleted]" or sub.title == "[deleted by user]":
                print(f"{sub.id=} message deleted {NOW_STR}")
                updated_df.at[index, "del_text_r"] = True
                updated_df.at[index, "del_text_r_utc"] = NOW_STR
        if sub.selftext == "[removed]":
            category_new = sub.removed_by_category
            if category_new is None:
                category_new = "False"
            category_old = row["removed_by_category_r"]
            if category_new != category_old:
                if pd.isna(row["rem_text_r_utc"]):
                    print(f"{sub.id=} removed {NOW_STR}")
                    updated_df.at[index, "rem_text_r"] = True
                    updated_df.at[index, "rem_text_r_utc"] = NOW_STR
                    updated_df.at[index, "removed_by_category_r"] = category_new
                if category_new == "deleted":
                    print("  changed to deleted!")
                    updated_df.at[index, "del_text_r"] = True
                    updated_df.at[index, "del_text_r_utc"] = NOW_STR
                    updated_df.at[index, "removed_by_category_r"] = category_new

    updated_fn = watched_fn.with_name(f"updated-{watched_fn.name}")
    updated_df.to_csv(updated_fn, index=True, encoding="utf-8-sig", na_rep="NA")
    return updated_fn


def rotate_archive_fns(updated_fn: Path) -> None:
    """Archive file to the zip file and rename it to be the latest."""
    print(f"Rotating and archiving {updated_fn=}")
    if not updated_fn.exists():
        raise RuntimeError(f"{updated_fn.exists()}")
    bare_fn = updated_fn.name.removeprefix("updated-").removesuffix(".csv")
    print(f"{bare_fn=}")
    stamped_fn = f"{bare_fn}-arch_{NOW.int_timestamp}.csv"
    print(f"{stamped_fn=}")
    zipped_fn = f"{bare_fn}-arch.zip"
    latest_fn = f"{bare_fn}.csv"
    print(f"{latest_fn=}")
    latest_path = updated_fn.parent / latest_fn
    stamped_path = updated_fn.parent / stamped_fn
    if latest_path.exists() and updated_fn.exists():
        print("rotating files")
        latest_path.rename(stamped_path)
        updated_fn.rename(latest_path)
    else:
        raise RuntimeError(f"{latest_path.exists()} {updated_fn.exists()}")
    zipped_path = updated_fn.parent / zipped_fn
    if zipped_path.exists():
        with zipfile.ZipFile(zipped_path, mode="a") as archive:
            print(f"adding {stamped_fn=} to {zipped_fn}")
            archive.write(stamped_path, arcname=stamped_fn)
        print(f"deleting {stamped_fn=}")
        stamped_path.unlink()
    else:
        log.critical(f"can't append stamped, {zipped_fn} not found")


def init_archive(updated_fn: Path) -> None:
    """Initialize the archive file with most recent version."""
    print(f"Initializing archive for {updated_fn=}")
    bare_fn = updated_fn.name.removeprefix("updated-").removesuffix(".csv")
    zipped_fn = updated_fn.parent / f"{bare_fn}-arch.zip"
    print(f"  creating archive {zipped_fn=}")

    with zipfile.ZipFile(zipped_fn, mode="w") as archive:
        archive.write(updated_fn, arcname=updated_fn.name)


def process_args(argv) -> argparse.Namespace:
    """Process arguments."""
    arg_parser = argparse.ArgumentParser(
        description=(
            "Watch the deletion/removal status of Reddit messages."
            + " Initialize subreddits to be watched first (e.g.,"
            + " 'Advice+AmItheAsshole). Schedule using cron or launchd"
        )
    )

    arg_parser.add_argument(
        "-i",
        "--init",
        type=str,
        default=False,
        help="""INITIALIZE `+` delimited subreddits to watch""",
    )
    arg_parser.add_argument(
        "--hours",
        type=int,
        default=24,
        help="""previous HOURS to fetch""",
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
            filename=f"{Path(__file__).name}.log",
            filemode="w",
            level=log_level,
            format=LOG_FORMAT,
        )
    else:
        log.basicConfig(level=log_level, format=LOG_FORMAT)

    return args


def main():
    args = process_args(sys.argv[1:])
    config = cp.ConfigParser(strict=False)

    if args.init:
        if not INI_FN.exists():
            INI_FN.write_text("[watching]")
        config.read(INI_FN)
        for subreddit in args.init.split("+"):
            watched_fn = init_watch_pushshift(subreddit, args.hours)
            config.set("watching", f"{subreddit}{NOW_STR[0:8]}", str(watched_fn))
            updated_fn = update_watch(watched_fn)
            init_archive(updated_fn)
            rotate_archive_fns(updated_fn)
        with INI_FN.open("w") as configfile:
            config.write(configfile)
    else:
        config.read(INI_FN)
        for _watched, fn in config["watching"].items():
            updated_fn = update_watch(Path(fn))
            rotate_archive_fns(updated_fn)


if __name__ == "__main__":
    main()
