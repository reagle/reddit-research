#!/usr/bin/env python3
"""Create a csv wherein each row corresponds to the queried subreddit name, its creation date in format YYYY-MM-DD, and its current number of members.

Resulting CSV can be used with `subreddit-plot`.
"""

__author__ = "Joseph Reagle"
__copyright__ = "Copyright (C) 2024 Joseph Reagle"
__license__ = "GLPv3"
__version__ = "0.1"

import argparse
import csv
import datetime
import sys
from pathlib import Path

import praw
import prawcore
import pytz

from reddit_research import web_utils

REDDIT = praw.Reddit(
    user_agent=web_utils.get_credential("REDDIT_USER_AGENT"),
    client_id=web_utils.get_credential("REDDIT_CLIENT_ID"),
    client_secret=web_utils.get_credential("REDDIT_CLIENT_SECRET"),
    username=web_utils.get_credential("REDDIT_USERNAME"),
    password=web_utils.get_credential("REDDIT_PASSWORD"),
    ratelimit_seconds=600,
)


def main() -> None:
    """Read subreddits from CSV, fetch information, write to new CSV."""
    args = process_args(sys.argv[1:])
    print(f"{args=}")
    input_file = args.input_file
    subreddits = list(csv.DictReader(input_file.open(newline="", encoding="utf-8")))
    output_file = input_file.with_stem(f"{input_file.stem}_info").with_suffix(".csv")

    # Create a CSV file and write headers
    with output_file.open("w", newline="", encoding="utf-8") as file:
        f = csv.writer(file)
        f.writerow(["subreddit", "created", "subscribers", "category"])

        # Iterate through subreddits and write data to the CSV file
        for subreddit in subreddits:
            try:
                sub = REDDIT.subreddit(subreddit["subreddit"])
                category = subreddit["category"]

                creation_date = datetime.datetime.fromtimestamp(
                    sub.created, pytz.UTC
                ).strftime("%Y-%m-%d")
                subscribers = sub.subscribers

                f.writerow([sub.display_name, creation_date, subscribers, category])
                print(f"Writing data for r/{sub.display_name}")
            except prawcore.PrawcoreException as err:
                print(f"Error fetching data for r/{subreddit['subreddit']}: {err}")
                # Write the name with null values for creation_date and subscribers
                f.writerow([subreddit["subreddit"], "", "", subreddit["category"]])


def process_args(argv) -> argparse.Namespace:
    arg_parser = argparse.ArgumentParser(
        description="Fetch subreddit information from a CSV file."
    )
    arg_parser.add_argument(
        "-i",
        "--input-file",
        type=Path,
        required=True,
        help="Path to the input CSV file containing subreddits.",
    )
    args = arg_parser.parse_args(argv)
    return args


if __name__ == "__main__":
    main()
