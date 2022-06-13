#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# DESCRIPTION
# This file is part of Reddit Tools
# <https://github.com/reagle/reddit/>
# (c) Copyright 2020-2022 by Joseph Reagle
# Licensed under the GPLv3, see <http://www.gnu.org/licenses/gpl-3.0.html>

import logging
import math
import os
import random
from typing import List, Tuple

import pendulum  # https://pendulum.eustace.io/docs/
import praw

from web_api_tokens import (
    REDDIT_CLIENT_ID,
    REDDIT_CLIENT_SECRET,
    REDDIT_USER_AGENT,
)

# https://github.com/reagle/thunderdell
from web_utils import get_JSON

# datetime: date, time, datetime, timedelta
# pendulum: datetime, Duration (timedelta), Period (Duration)


REDDIT = praw.Reddit(
    user_agent=REDDIT_USER_AGENT,
    client_id=REDDIT_CLIENT_ID,
    client_secret=REDDIT_CLIENT_SECRET,
    ratelimit_seconds=600,
)

HOMEDIR = os.path.expanduser("~")

log = logging.getLogger("reddit_sample")
exception = logging.exception
critical = logging.critical
error = logging.error
warning = logging.warning
info = logging.info
debug = logging.debug


def is_overlapping(
    offsets: list, PUSHSHIFT_LIMIT: int, results_per_hour: int
) -> bool:
    """If I grab PUSHSHIFT_LIMIT results at an offset hour, am I
    enough hours in the future from the last offset hour to avoid
    overlap"""

    last = None
    hours_needed = math.ceil(PUSHSHIFT_LIMIT / results_per_hour)
    info(f"{offsets=}")
    warning(f"{hours_needed=} between each offset")
    for offset in offsets:
        if last is None:  # initial offset, so proceed to next
            last = offset
            continue
        info(f"  {offset} - {last} = {offset - last}")
        if offset - last > hours_needed:
            last = offset
            continue
        else:
            critical(
                f"  overlap:"
                f"  offsets {offset} - {last} is not less than {hours_needed}"
                f" "
            )
            return True
    return False


def get_pushshift_total(
    subreddit: str,
    after: pendulum.DateTime,
    before: pendulum.DateTime,
) -> int:
    info(f"after = {after.format('YYYY-MM-DD HH:mm:ss ZZ')}")
    after_epoch = int(after.int_timestamp)
    info(f"{after_epoch=}")
    info(f"before = {before.format('YYYY-MM-DD HH:mm:ss ZZ')}")
    before_epoch = int(before.int_timestamp)
    info(f"{before_epoch=}")
    PUSHSHIFT_META_URL = (
        f"https://api.pushshift.io/reddit/submission/search/"
        f"?subreddit={subreddit}&after={after_epoch}&before={before_epoch}"
        f"&size=0&metadata=true"
    )
    info(f"{PUSHSHIFT_META_URL=}")
    results_total = get_JSON(PUSHSHIFT_META_URL)["metadata"]["total_results"]
    info(f"{results_total=}")
    return results_total


def get_cacheable_randos(size: int, samples: int, seed: int):
    """Return k=samples of random integers in range up to `size` such that a
    larger sample result includes smaller sample results.
    >>> get_cacheable_randos(50, 5, seed=7)
    [3, 9, 20, 25, 41]
    >>> get_cacheable_randos(50, 10, seed=7)
    [3, 4, 6, 9, 20, 23, 25, 34, 37, 41]
    >>> get_cacheable_randos(50, 15, seed=7)
    [2, 3, 4, 5, 6, 9, 13, 20, 23, 25, 32, 34, 37, 41, 45]
    """
    random.seed(seed)
    return sorted(random.sample(range(size), samples))


def get_offsets(
    subreddit: str,
    after: pendulum.DateTime,
    before: pendulum.DateTime,
    sample_size: int,
    PUSHSHIFT_LIMIT: int,
) -> Tuple[int, List[pendulum.DateTime]]:
    """For sampling, return a set of hourly offsets, beginning near
    after, that should not overlap"""

    duration = before - after
    info(f"{duration.in_days()=}")
    info(f"{duration.in_hours()=}")
    info(f"{duration.in_weeks()=}")
    results_total = get_pushshift_total(subreddit, after, before)
    results_per_hour = math.ceil(results_total / duration.in_hours())
    info(f"{results_per_hour=} on average")

    info(f"{PUSHSHIFT_LIMIT=}")
    info(f"{sample_size=}")
    queries_total = math.ceil(sample_size / PUSHSHIFT_LIMIT)
    info(f"{queries_total=}")
    info(f"{range(duration.in_hours())=}")

    SEEDS_TO_TRY = 5
    seed = int(after.timestamp())
    for seed_counter in range(SEEDS_TO_TRY):
        seed += seed_counter  # increment seed
        warning(f"attempt {seed_counter} to find non-overlapping offsets")
        offsets = get_cacheable_randos(
            duration.in_hours(), queries_total, seed
        )
        if is_overlapping(offsets, PUSHSHIFT_LIMIT, results_per_hour):
            critical(f"  seed attempt {seed_counter} failed")
            continue
        else:
            break
    else:
        print(
            f"I exhausted random sets of offsets at {SEEDS_TO_TRY=}"
            f"Quitting because I'm too likely to pull overlapping results"
        )
        raise RuntimeError

    offsets_as_datetime = []
    for offset_as_hour in offsets:
        offset_as_datetime = after.add(hours=offset_as_hour)
        offsets_as_datetime.append(offset_as_datetime)
    info(f"{len(offsets)=}")
    return offsets_as_datetime


if __name__ == "__main__":

    exception = critical = error = warning = info = debug = info = print

    start = "2022-01-01"
    end = "2022-06-10"
    after: pendulum.DateTime = pendulum.parse(start)
    before: pendulum.DateTime = pendulum.parse(end)
    print(f"{before.timezone.name=}")

    sample_size = 5000
    PUSHSHIFT_LIMIT = 100

    total, offsets = get_offsets(
        "AmItheAsshole", after, before, sample_size, PUSHSHIFT_LIMIT
    )
    for count, offset in enumerate(sorted(offsets)):
        print(f"{count: <5} {offset.to_datetime_string()=}")
    print(
        f"\n{total=:,} messages between"
        f" {after.to_datetime_string()} and {before.to_datetime_string()}\n"
        f"   across {len(offsets)} offsets,"
        f" at {PUSHSHIFT_LIMIT} messages per offset,"
        f" for {sample_size} message samples\n"
        f"   a {sample_size/total:.0%} sample"
    )

    import doctest

    doctest.testmod()
