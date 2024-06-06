#!/usr/bin/env python3
"""
Find the usernames of commenters associated with submissions title and subreddits.
Read a CSV file of Reddit submission titles and use PRAW to find the URL of each post.
For each URL, fnd the usernames of users who commented on that post.
The input CSV file has columns for subreddit and title.
The output CSV file has columns for subreddit, title, and author_p.
"""

import argparse
import csv
import sys
from pathlib import Path

import cachier
import praw
from tqdm import tqdm

import web_api_tokens as wat

__author__ = "Joseph Reagle"
__copyright__ = "Copyright (C) 2024 Joseph Reagle"
__license__ = "GLPv3"
__version__ = "0.1"


# Create a Reddit instance
REDDIT = praw.Reddit(
    user_agent=wat.REDDIT_USER_AGENT,
    client_id=wat.REDDIT_CLIENT_ID,
    client_secret=wat.REDDIT_CLIENT_SECRET,
    username=wat.REDDIT_USERNAME,
    password=wat.REDDIT_PASSWORD,
    ratelimit_seconds=600,
)


def process_args(argv: list) -> argparse.Namespace:
    """Process command-line arguments using argparse."""

    parser = argparse.ArgumentParser(
        description="Find URLs for Reddit posts from a csv file."
    )
    parser.add_argument(
        "input_csv", type=Path, help="csv file containing Reddit posts."
    )
    return parser.parse_args(argv)


@cachier.cachier(pickle_reload=False)  # stale_after=dt.timedelta(days=7)
def get_post_url(subreddit: str, title: str) -> str:
    """Search for a post in a subreddit by title and return its URL."""
    for submission in REDDIT.subreddit(subreddit).search(title, limit=1):
        return submission.url
    return ""


@cachier.cachier(pickle_reload=False)  # stale_after=dt.timedelta(days=7)
def get_commenters(url: str) -> list[str]:
    """Get the usernames of users who commented on a given post."""
    submission = REDDIT.submission(url=url)
    usernames = [
        comment.author.name
        for comment in submission.comments.list()
        if isinstance(comment, praw.models.Comment) and comment.author  # type: ignore
    ]
    return usernames


def process_submissions(input_csv: Path) -> list[dict[str, str]]:
    data = []

    with input_csv.open(newline="") as csvfile:
        reader = csv.DictReader(csvfile)
        total_rows = sum(1 for _ in reader)
        csvfile.seek(0)  # Reset the file pointer to the beginning

        progress_bar = tqdm(total=total_rows, desc="Processing submissions")

        for row in reader:
            subreddit = row["subreddit"]
            title = row["title"]
            url = get_post_url(subreddit, title)
            usernames = []
            if url:
                usernames = get_commenters(url)
                data.append(
                    {"subreddit": subreddit, "title": title, "usernames": usernames}
                )

            progress_bar.set_description(
                f"Processing submissions (Found {len(usernames)} usernames)"
            )
            progress_bar.update(1)

        progress_bar.close()

    return data


def save_to_csv(data: list[dict[str, str]], output_path: Path):
    fieldnames = ["subreddit", "title", "author_p"]
    output_path = Path(output_path)

    with output_path.open("w", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        for item in data:
            subreddit = item["subreddit"]
            title = item["title"]
            usernames = item["usernames"]

            for username in usernames:
                writer.writerow(
                    {"subreddit": subreddit, "title": title, "author_p": username}
                )


if __name__ == "__main__":
    args = process_args(sys.argv[1:])
    results = process_submissions(args.input_csv)
    csv_output = Path(f"{args.input_csv.stem}-usernames.csv")
    save_to_csv(results, csv_output)
