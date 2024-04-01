#!/usr/bin/env python3
"""
Create a csv wherein each row corresponds to the queried subreddit name, its creation date in format YYYY-MM-DD, and its current number of members.

Resulting CSV can be used with `subreddit-plot.py`.
"""

__author__ = "Joseph Reagle"
__copyright__ = "Copyright (C) 2024 Joseph Reagle"
__license__ = "GLPv3"
__version__ = "0.1"

import csv
import datetime

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

# List of subreddits
subreddits = [
    {"name": "Advice", "category": "general"},
    {"name": "AdviceAnimals", "category": "funny"},
    {"name": "AITAH", "category": "judgement"},
    {"name": "AmItheAsshole", "category": "judgement"},
    {"name": "AmItheButtface", "category": "judgement"},
    {"name": "amiwrong", "category": "judgement"},
    {"name": "ask", "category": "general"},
    {"name": "AskDocs", "category": "health"},
    {"name": "askmen", "category": "gender"},
    {"name": "AskReddit", "category": "general"},
    {"name": "AskWomen", "category": "gender"},
    {"name": "askwomenadvice", "category": "gender"},
    {"name": "dating_advice", "category": "relationship"},
    {"name": "DiagnoseMe", "category": "health"},
    {"name": "health_advice", "category": "health", "creation_date": "2009-09-28", "subscribers": 0},
    {"name": "Healthadvice", "category": "health"},
    {"name": "medical", "category": "health"},
    {"name": "medical_advice", "category": "health"},
    {"name": "needadvice", "category": "general"},
    {"name": "relationship_advice", "category": "relationship"},
    {"name": "relationships", "category": "relationship"},
]

# Create a CSV file and write headers
with open("subreddit_info.csv", "w", newline="", encoding="utf-8") as file:
    f = csv.writer(file)
    f.writerow(["subreddit", "created", "subscribers", "category"])

    # Iterate through subreddits and write data to the CSV file
    for subreddit in subreddits:
        try:
            sub = REDDIT.subreddit(subreddit["name"])
            category = subreddit["category"]

            # Fetch creation_date and subscribers only if not already provided
            if "creation_date" not in subreddit:
                creation_date = datetime.datetime.fromtimestamp(
                    sub.created, pytz.UTC
                ).strftime("%Y-%m-%d")
            else:
                creation_date = subreddit["creation_date"]

            if "subscribers" not in subreddit:
                subscribers = sub.subscribers
            else:
                subscribers = subreddit["subscribers"]

            f.writerow([sub.display_name, creation_date, subscribers, category])
            print(f"Writing data for r/{sub.display_name}")
        except Exception as e:
            print(f"Error while fetching data for r/{subreddit['name']}: {e}")
            # Write the name with null values for creation_date and subscribers
            f.writerow([subreddit["name"], "", "", subreddit["category"]])