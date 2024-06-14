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
import re
import string
import sys
from pathlib import Path

import cachier
import jsonlines
import praw
import zstandard as zstd
from rapidfuzz import fuzz
from tqdm import tqdm  # type: ignore

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
        description="Find URLs and commenters for Reddit posts."
    )
    parser.add_argument(
        "input_csv", type=Path, help="csv file containing Reddit posts."
    )
    return parser.parse_args(argv)


def decompress_file(compressed_file: Path) -> Path:
    """Decompress a zstd compressed file."""
    decompressed_file = compressed_file.with_suffix("")  # removes ".zst"

    if not decompressed_file.exists():
        with open(compressed_file, "rb") as compressed, open(
            decompressed_file, "wb"
        ) as decompressed:
            print(f"decompressing {compressed_file}")
            dctx = zstd.ZstdDecompressor()
            reader = dctx.stream_reader(compressed)
            decompressed.write(reader.read())

    return decompressed_file


@cachier.cachier(pickle_reload=False)  # stale_after=dt.timedelta(days=7)
def count_lines(file_path: Path) -> int:
    with open(file_path) as f:
        return sum(1 for _ in f)


@cachier.cachier(pickle_reload=False)  # stale_after=dt.timedelta(days=7)
def api_get_post_url(subreddit: str, title: str) -> tuple[str, str]:
    """Search for a post in a subreddit by title and return its URL."""
    # NOTE: I'm not using this presently since the Reddit API won't
    # return titles of deleted or removed messages.
    for submission in REDDIT.subreddit(subreddit).search(title, limit=1):
        return (submission.title, submission.url)
    return ("", "")


@cachier.cachier(pickle_reload=False)  # stale_after=dt.timedelta(days=7)
def jsonl_get_post_url(subreddit: str, title: str) -> tuple[str, str]:
    """Given the name of a subreddit, see if the file "{DUMPS_Path}/{subreddit}_submissions.jsonl.zst" exists;
    If the file exists, decompress it and search for the title.
    If the title is found, return the title and corresponding URL.
    """
    DUMPS_PATH = Path("~/data/1work/2020/advice/subreddits/").expanduser()

    compressed_file = DUMPS_PATH / f"{subreddit}_submissions.jsonl.zst"

    if not compressed_file.exists():
        print(f"NOT found: {compressed_file}")
        return ("", "")

    decompressed_file = decompress_file(compressed_file)
    total_lines = count_lines(decompressed_file)

    with jsonlines.open(decompressed_file) as reader:
        print(f"Checking {decompressed_file}")
        print(f"Looking for: {title}")

        for obj in tqdm(reader, total=total_lines):
            similarity_ratio = fuzz.ratio(obj["title"], title)
            if similarity_ratio > 95:
                print(f"\nFOUND with {similarity_ratio}:")
                print(f"  {title}")
                print(f"  {obj['title']}")
                return obj["title"], obj["url"]

        print(f"NOT found: {title}")
        return (title, "")


# jsonl_get_post_url.clear_cache()


@cachier.cachier(pickle_reload=False)  # stale_after=dt.timedelta(days=7)
def api_get_commenters(url: str) -> list[str]:
    """Get the usernames of users who commented on a given post."""
    submission = REDDIT.submission(url=url)
    usernames = [
        comment.author.name
        for comment in submission.comments.list()
        if isinstance(comment, praw.models.Comment) and comment.author  # type: ignore
    ]
    return usernames


def process_submissions(input_csv: Path) -> list[dict[str, str]]:
    """Process the input CSV file to find URLs and commenters.
    Because Reddit always returns, check if the queried and returned
    title are sufficiently close."""
    data = []

    with input_csv.open(newline="") as csvfile:
        reader = csv.DictReader(csvfile)
        total_rows = sum(1 for _ in reader)
        csvfile.seek(0)  # Reset the file pointer to the beginning

        progress_bar = tqdm(total=total_rows, desc="Processing submissions")

        for row in reader:
            subreddit = row["subreddit"]
            usernames = ["null20240614"]
            diff_ratio = 0
            title = row["title"]
            submission_url = ""

            submission_title, submission_url = jsonl_get_post_url(subreddit, title)

            if submission_url:
                # not the actual title, probably deleted
                diff_ratio = fuzz.ratio(title, submission_title)
                if diff_ratio < 90:
                    submission_url = ""
                else:
                    usernames = api_get_commenters(submission_url)
            data.append(
                {
                    "subreddit": subreddit,
                    "usernames": usernames,
                    "diff_ratio": diff_ratio,
                    "title": title,
                    "url": submission_url,
                }
            )

            progress_bar.set_description(
                f"Processing submissions (Found {len(usernames)} usernames)"
            )
            progress_bar.update(1)

        progress_bar.close()

    return data


def save_to_csv(data: list[dict[str, str]], output_path: Path):
    fieldnames = ["subreddit", "author_p", "diff_ratio", "title", "url"]
    output_path = Path(output_path)

    with output_path.open("w", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        for item in data:
            for username in item["usernames"]:
                writer.writerow(
                    {
                        "subreddit": item["subreddit"],
                        "author_p": username,
                        "diff_ratio": item["diff_ratio"],
                        "title": item["title"],
                        "url": item["url"],
                    }
                )


if __name__ == "__main__":
    args = process_args(sys.argv[1:])
    results = process_submissions(args.input_csv)
    csv_output = Path(f"{args.input_csv.stem}-usernames.csv")
    save_to_csv(results, csv_output)
