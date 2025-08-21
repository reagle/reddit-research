#!/usr/bin/env python3
# /// script
# requires-python = ">=3.13"
# dependencies = [
#   "praw",
#   "python-dotenv",
# ]
# ///
"""Fetch all posts from a Reddit user and export to CSV."""

import argparse
import csv
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import praw
from praw.models import Redditor, Submission

from reddit_research.web_utils import get_credential


def process_args(argv: list[str] | None) -> argparse.Namespace:
    """Process command line arguments.

    Returns parsed arguments namespace with username and output file.
    """
    parser = argparse.ArgumentParser(
        description="Fetch all posts from a Reddit user and export to CSV"
    )
    parser.add_argument("username", help="Reddit username (without u/ prefix)")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Output CSV file (default: username_posts.csv)",
    )
    parser.add_argument(
        "-l",
        "--limit",
        type=int,
        default=None,
        help="Maximum number of posts to fetch (default: all)",
    )

    return parser.parse_args(argv)


def initialize_reddit() -> praw.Reddit:
    """Initialize Reddit API connection using credentials.

    Returns configured Reddit instance.
    """
    return praw.Reddit(
        client_id=get_credential("REDDIT_CLIENT_ID"),
        client_secret=get_credential("REDDIT_CLIENT_SECRET"),
        user_agent=get_credential("REDDIT_USER_AGENT"),
    )


def fetch_user_posts(
    reddit: praw.Reddit, username: str, limit: int | None = None
) -> list[dict[str, Any]]:
    """Fetch all posts from a Reddit user.

    Returns list of post dictionaries with title, date, and URL.
    """
    try:
        redditor: Redditor = reddit.redditor(username)
        # Test if user exists by accessing a property
        _ = redditor.id
    except Exception as e:
        raise ValueError(f"Unable to access user '{username}': {e}")

    posts: list[dict[str, Any]] = []

    for submission in redditor.submissions.new(limit=limit):
        post_data = {
            "title": submission.title,
            "date": datetime.fromtimestamp(submission.created_utc).strftime("%Y-%m-%d"),
            "url": f"https://reddit.com{submission.permalink}",
        }
        posts.append(post_data)

    return posts


def write_csv(posts: list[dict[str, Any]], output_path: Path) -> None:
    """Write posts data to CSV file.

    Creates CSV with title, date, and URL columns.
    """
    if not posts:
        print("No posts found to write.", file=sys.stderr)
        return

    with output_path.open("w", newline="", encoding="utf-8") as csvfile:
        fieldnames = ["title", "date", "url"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        writer.writeheader()
        writer.writerows(posts)


def main(argv: list[str] | None = None) -> int:
    """Start in main entry point.

    Returns exit code (0 for success, 1 for error).
    """
    args = process_args(argv)

    # Set default output filename if not specified
    output_path = args.output or Path(f"{args.username}_posts.csv")

    try:
        # Initialize Reddit API
        reddit = initialize_reddit()

        # Fetch user posts
        print(f"Fetching posts for u/{args.username}...", file=sys.stderr)
        posts = fetch_user_posts(reddit, args.username, args.limit)

        # Write to CSV
        write_csv(posts, output_path)

        print(
            f"Successfully wrote {len(posts)} posts to {output_path}", file=sys.stderr
        )
        return 0

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
