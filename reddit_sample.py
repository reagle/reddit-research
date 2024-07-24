"""Sample messages over significant spans, used by `reddit-query.py`.

Reddit itself doesn't  permit date-ranges, so I have to pull data from
Pushshift, estimate how many chunks (PUSHSHIFT_LIMIT) to take at hourly
offsets within the range, including the ability to sample throughout
the range.
"""

__author__ = "Joseph Reagle"
__copyright__ = "Copyright (C) 2009-2023 Joseph Reagle"
__license__ = "GLPv3"
__version__ = "1.0"

import logging
import math
import random

import cachier
import numpy as np
import Path
import pendulum  # https://pendulum.eustace.io/docs/
import praw

import web_api_tokens as wat
import web_utils  # https://github.com/reagle/thunderdell

# datetime: date, time, datetime, timedelta
# pendulum: datetime, Duration (timedelta), Period (Duration)


REDDIT = praw.Reddit(
    user_agent=wat.REDDIT_USER_AGENT,
    client_id=wat.REDDIT_CLIENT_ID,
    client_secret=wat.REDDIT_CLIENT_SECRET,
    ratelimit_seconds=600,
)

HOMEDIR = Path.home()

log = logging.getLogger("reddit_sample")
log.exception = logging.exception
log.critical = logging.critical
log.error = logging.error
log.warning = logging.warning
log.info = logging.info
log.debug = logging.debug


def is_overlapping(offsets: list, PUSHSHIFT_LIMIT: int, results_per_hour: int) -> bool:
    """
    If I grab PUSHSHIFT_LIMIT results at an offset hour, am I enough
    hours in the future from the last offset hour to avoid overlap
    """

    last = None
    hours_needed = math.ceil(PUSHSHIFT_LIMIT / results_per_hour)
    log.info(f"{offsets=}")
    log.warning(f"{hours_needed=} between each offset")
    for offset in offsets:
        if last is None:  # initial offset, so proceed to next
            last = offset
            continue
        log.info(f"  {offset} - {last} = {offset - last}")
        if offset - last > hours_needed:
            last = offset
            continue
        else:
            log.critical(
                "  overlap:"
                f"  offsets {offset} - {last} is not less than {hours_needed}"
                " "
            )
            return True
    return False


@cachier.cachier(pickle_reload=False)  # stale_after=dt.timedelta(days=7)
def get_pushshift_total(
    subreddit: str,
    after: pendulum.DateTime,
    before: pendulum.DateTime,
) -> int:
    """Get the total number of results in a Pushshift query via the
    '&metadata=true' parameter"""
    log.info("*************")
    log.info(f"after = {after.format('YYYY-MM-DD HH:mm:ss ZZ')}")
    after_epoch = int(after.int_timestamp)
    log.info(f"{after_epoch=}")
    log.info(f"before = {before.format('YYYY-MM-DD HH:mm:ss ZZ')}")
    before_epoch = int(before.int_timestamp)
    log.info(f"{before_epoch=}")
    PUSHSHIFT_META_URL = (
        "https://api.pushshift.io/reddit/submission/search/"
        f"?subreddit={subreddit}&after={after_epoch}&before={before_epoch}"
        "&size=0&metadata=true"
    )
    log.info(f"{PUSHSHIFT_META_URL=}")
    # TODO: adapt to API change
    # https://www.reddit.com/r/pushshift/comments/109ckav/did_the_api_change/
    # https://www.reddit.com/r/pushshift/comments/zkggt0/update_on_colo_switchover_bug_fixes_reindexing/
    results_total = web_utils.get_JSON(PUSHSHIFT_META_URL)["metadata"]["total_results"]
    log.info(f"{results_total=}")
    return results_total


def get_sequence(size: int, samples: int) -> list[int]:
    """Return [0,size, k=samples). This is not very cacheable as different
    sample sizes generate different offsets."""

    step = math.ceil(size / samples)
    return list(range(0, size, step))


def get_cacheable_np_randos(size: int, samples: int, seed: int):
    """Return k=samples of random integers in range up to `size` such that a
    larger sample result includes smaller sample results. Using numpy"""

    # random.seed(seed)
    return sorted(np.random.randint(low=0, high=size + 1, size=samples))


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
    # TODO: Replace with low-discrepancy, quasi-random numbers
    # (qmc.Sobol.integers() is forthcoming in scipy 1.9)

    random.seed(seed)
    return sorted(random.sample(range(size), samples))


def get_offsets(
    subreddit: str,
    after: pendulum.DateTime,
    before: pendulum.DateTime,
    sample_size: int,
    PUSHSHIFT_LIMIT: int,
) -> list[pendulum.DateTime]:
    """For sampling, return a set of hourly offsets, beginning near
    after, that should not overlap"""

    duration = before - after
    log.info(f"{duration.in_days()=}")
    log.info(f"{duration.in_hours()=}")
    log.info(f"{duration.in_weeks()=}")
    results_total = get_pushshift_total(subreddit, after, before)
    results_per_hour = math.ceil(results_total / duration.in_hours())
    log.info(f"{results_per_hour=} on average")

    log.info(f"{PUSHSHIFT_LIMIT=}")
    log.info(f"{sample_size=}")
    queries_total = math.ceil(sample_size / PUSHSHIFT_LIMIT)
    log.info(f"{queries_total=}")
    log.info(f"{range(duration.in_hours())=}")

    SEEDS_TO_TRY = 300
    seed = int(after.timestamp())
    for seed_counter in range(SEEDS_TO_TRY):
        seed += seed_counter  # increment seed
        log.warning(f"attempt {seed_counter} to find non-overlapping offsets")
        offsets = get_cacheable_randos(duration.in_hours(), queries_total, seed)
        if is_overlapping(offsets, PUSHSHIFT_LIMIT, results_per_hour):
            log.critical(f"  seed attempt {seed_counter} failed")
            continue
        else:
            break
    else:
        print(
            f"I exhausted random sets of offsets at {SEEDS_TO_TRY=}"
            "Quitting because I'm too likely to pull overlapping results"
        )
        raise RuntimeError

    offsets_as_datetime = []
    for offset_as_hour in offsets:
        offset_as_datetime = after.add(hours=offset_as_hour)
        offsets_as_datetime.append(offset_as_datetime)
    log.info(f"{len(offsets)=}")
    return offsets_as_datetime


if __name__ == "__main__":
    start = "2022-01-01"
    end = "2022-06-10"
    after: pendulum.DateTime = pendulum.parse(start)
    before: pendulum.DateTime = pendulum.parse(end)
    print(f"{before.timezone.name=}")

    sample_size = 5000
    PUSHSHIFT_LIMIT = 100

    total = get_pushshift_total("AmItheAsshole", after, before)
    offsets = get_offsets("AmItheAsshole", after, before, sample_size, PUSHSHIFT_LIMIT)
    for count, offset in enumerate(sorted(offsets)):
        log.info(f"{count: <5} {offset.to_datetime_string()=}")
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

    print(f"{get_sequence(size=3840, samples=15)=}")
    print(f"{get_cacheable_randos(100, 10, seed=7)=}")
    print(f"{get_cacheable_np_randos(100, 10, seed=7)=}")

    print(f"{get_pushshift_total('Advice', after, before)=}")
    print(f"{get_pushshift_total('AmItheAsshole', after, before)=}")
    print(f"{get_pushshift_total('relationship_advice', after, before)=}")
