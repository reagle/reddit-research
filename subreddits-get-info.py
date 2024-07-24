#!/usr/bin/env python3
"""
Create a csv wherein each row corresponds to the queried subreddit name, its creation date in format YYYY-MM-DD, and its current number of members.

Resulting CSV can be used with `subreddit-plot.py`.
"""

__author__ = "Joseph Reagle"
__copyright__ = "Copyright (C) 2024 Joseph Reagle"
__license__ = "GLPv3"
__version__ = "0.1"

import argparse
import csv
import datetime
from pathlib import Path

import praw
import pytz

import web_api_tokens as wat

# Create a Reddit instance
REDDIT = praw.Reddit(
    user_agent=wat.REDDIT_USER_AGENT,
    client_id=wat.REDDIT_CLIENT_ID,
    client_secret=wat.REDDIT_CLIENT_SECRET,
    username=wat.REDDIT_USERNAME,
    password=wat.REDDIT_PASSWORD,
    ratelimit_seconds=600,
)


def main(input_file: Path) -> None:
    # Read subreddits from the input CSV file
    subreddits = list(csv.DictReader(input_file.open(newline="", encoding="utf-8")))

    # Create the output file path by appending "_info" to the input file name
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
            except Exception as e:
                print(f"Error while fetching data for r/{subreddit['subreddit']}: {e}")
                # Write the name with null values for creation_date and subscribers
                f.writerow([subreddit["subreddit"], "", "", subreddit["category"]])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Fetch subreddit information from a CSV file."
    )
    parser.add_argument(
        "-i",
        "--input",
        type=Path,
        required=True,
        help="Path to the input CSV file containing subreddits.",
    )
    args = parser.parse_args()

    main(args.input)
