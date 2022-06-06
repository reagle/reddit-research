#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# DESCRIPTION
# This file is part of Reddit Tools
# <https://github.com/reagle/reddit/>
# (c) Copyright 2020-2022 by Joseph Reagle
# Licensed under the GPLv3, see <http://www.gnu.org/licenses/gpl-3.0.html>

import arrow
import logging
import math
import os
import praw
import random

# import sys

from web_api_tokens import (
    REDDIT_CLIENT_ID,
    REDDIT_CLIENT_SECRET,
    REDDIT_USER_AGENT,
)

# https://github.com/reagle/thunderdell
from web_utils import get_JSON


REDDIT = praw.Reddit(
    user_agent=REDDIT_USER_AGENT,
    client_id=REDDIT_CLIENT_ID,
    client_secret=REDDIT_CLIENT_SECRET,
    ratelimit_seconds=600,
)

HOMEDIR = os.path.expanduser("~")

log = logging.getLogger("web_utils")
critical = logging.critical
info = logging.info
dbg = logging.debug


def get_offsets(
    after: int, before: int, sample_size: int, PUSHSHIFT_LIMIT: int
) -> list[int]:
    """For sampling, return a set of time offsets, beginning with
    after that should not overlap"""

    def is_overlapping(
        offsets: list, PUSHSHIFT_LIMIT: int, results_per_hour: int
    ) -> bool:
        """If I grab PUSHSHIFT_LIMIT results at an offset, am enough
        hours in the future from the last not get redundant results"""
        last = None
        hours_needed = math.ceil(PUSHSHIFT_LIMIT / results_per_hour)
        info(f"{hours_needed=}")
        for offset in offsets:
            if last is None:
                last = offset
                continue
            info(f"{offset=}, {last=}, {offset - last=}")
            if offset - last > hours_needed:
                info(f"  okay")
            else:
                info(f"  possible overlap!")
                return True
            last = offset
        return False

    info(f"after = {after.format('YYYY-MM-DD HH:mm:ss ZZ')}")
    after_epoch = after.int_timestamp
    info(f"{after_epoch=}")
    info(f"before = {before.format('YYYY-MM-DD HH:mm:ss ZZ')}")
    before_epoch = before.int_timestamp
    info(f"{before_epoch=}")
    duration = before - after
    info(f"{duration.days} days")
    duration_hours = duration.days * 24
    info(f"{duration_hours} hours")

    pushshift_url = (
        f"https://api.pushshift.io/reddit/submission/search/"
        f"?subreddit=Advice&after={after_epoch}&before={before_epoch}"
        f"&size=0&metadata=true"
    )
    info(f"{pushshift_url=}")

    total_results = get_JSON(pushshift_url)["metadata"]["total_results"]
    info(f"{total_results=}")

    results_per_hour = math.ceil(total_results / duration_hours)
    info(f"{results_per_hour=} on average")

    info(f"{PUSHSHIFT_LIMIT=}")
    info(f"{sample_size=}")
    queries_total = math.ceil(sample_size / PUSHSHIFT_LIMIT)
    info(f"{queries_total=}")
    info(f"{range(duration_hours)=}")

    SEED_LIMIT = 5
    deterministic_seeds = range(SEED_LIMIT)  # 5 chances, otherwise too crowded
    for seed in deterministic_seeds:
        random.seed(seed)
        offsets = sorted(random.sample(range(duration_hours), k=queries_total))
        info(f"{offsets=} at hours from after")
        info(f"{is_overlapping(offsets, PUSHSHIFT_LIMIT, results_per_hour)=}")
        if is_overlapping(offsets, PUSHSHIFT_LIMIT, results_per_hour):
            continue
        else:
            break
    else:
        print(
            f"I exhausted random sets of offsets at {SEED_LIMIT=}"
            f"Quitting because I'm too likely to pull overlapping results"
        )
        raise RuntimeError

    return offsets


if __name__ == "__main__":
    after = arrow.get("2022-06-01", "YYYY-MM-DD")
    before = arrow.get("2022-06-02", "YYYY-MM-DD")
    sample_size = 200
    PUSHSHIFT_LIMIT = 100

    print(f"{get_offsets(after, before, sample_size, PUSHSHIFT_LIMIT)=}")
    for offset in get_offsets(after, before, sample_size, PUSHSHIFT_LIMIT):
        offset_datetime = after.shift(hours=offset)
        print(f"{offset_datetime=}")
        offset_datetime_epoch = offset_datetime.int_timestamp
        print(f"  {offset_datetime_epoch=}")
