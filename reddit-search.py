#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# (c) Copyright 2020 by Joseph Reagle
# Licensed under the GPLv3, see <http://www.gnu.org/licenses/gpl-3.0.html>
# Given a spreadsheet with phrases, facilitate a search of those
# appearing in a column by opening browser windows to relevant search engines.

import argparse  # http://docs.python.org/dev/library/argparse.html
import logging
import sys
import time
import webbrowser
from os import name, system
from pathlib import Path  # https://docs.python.org/3/library/pathlib.html
from urllib.parse import urlparse

import pandas as pd
import requests

HOME = str(Path("~").expanduser())

exception = logging.exception
critical = logging.critical
error = logging.error
warning = logging.warning
info = logging.info
debug = logging.debug


def auto_search(subreddit, quote, target_url):
    """Does the URL appear in the query results?"""
    response = requests.get(query)
    if target_url in response.text:
        debug(f"found at {query=}")
        return True
    return False


def quotes_search(row, heading, do_recheck):
    """Open browser on each search engine to help find quotes."""

    system("cls") if name == "nt" else system("clear")
    if row[heading] == "" or "found" not in row:
        return
    info(f"{row['found']=}")
    if do_recheck or row["found"] == "" or pd.isnull(row["found"]):
        info(f"checking")
        original_quote = row[heading]
        print(f"{original_quote}\n")
        if row["subreddit"]:
            subreddit = f"r/{row['subreddit']}/"
        else:
            subreddit = ""
        debug("-------------------------")
        debug(f"{row['key']}, {row['original']}\n")

        # Google query
        query_google = (
            """https://www.google.com/search"""
            """?q=site:reddit.com {subreddit} {original_quote}"""
        )
        auto_search(subreddit, original_quote, row["url"])
        query_google_final = query_google.format(
            subreddit=subreddit, original_quote=original_quote
        )
        debug(f"Google query:       {query_google_final}")
        webbrowser.open(query_google)
        time.sleep(0.5)

        # Reddit query
        query_reddit = (
            f"""https://www.reddit.com/{subreddit}search/"""
            f"""?q={original_quote}&restrict_sr=on&include_over_18=on"""
        )
        debug(f"Reddit query:       {query_reddit_final}")
        webbrowser.open(query_reddit)
        time.sleep(0.5)

        # Pushshift query
        # or another interface: https://camas.github.io/reddit-search/
        query_pushshift = (
            f"""https://redditsearch.io/"""
            f"""?term={original_quote}&dataviz=false&aggs=false"""
            f"""&subreddits={subreddit[2:-1]}&searchtype=posts,comments"""
            f"""&search=true&start=0&end=1594758200&size=100"""
        )
        debug(f"Pushshift query:       {query_pushshift_final}")
        webbrowser.open(query_pushshift)

        character = input("`enter` to continue | `q` to quit: ")

        if character == "q":
            sys.exit()


def grab_quotes(file_name, column, do_recheck):
    """Read a column of quotes from a spreadsheet."""

    info(f"{file_name=}, {column=}, {do_recheck=}")
    suffix = Path(file_name).suffix
    if suffix in [".xls", ".xlsx", ".odf", ".ods", ".odt"]:
        df = pd.read_excel(file_name, keep_default_na=False)
        # key, subreddit, type, original, found
        # key, subreddit, type, original, spintax, spinrewriter, found
        # key, subreddit, type, original, wordai, found
        for counter, row in df.iterrows():
            quotes_search(row, column, do_recheck)

    elif suffix in [".csv"]:
        df = pd.read_csv(file_name, delimiter=",", keep_default_na=False)
        # key, directive, method, original, found, url, species, source, comment
        for counter, row in df.iterrows():
            quotes_search(row, column, do_recheck)
    else:
        print(f"{file_name}")
        raise ValueError("unknown file type/extension")
        sys.exit()


def main(argv):
    """Process arguments"""
    arg_parser = argparse.ArgumentParser(
        formatter_class=argparse.RawTextHelpFormatter,
        description="""        Given a spreadsheet with phrases, facilitate a
        search of those appearing in a column by opening browser windows to
        relevant search engines. For example:
        > reddit-search.py reddit-mask-quotes.csv -c original
        > reddit-search.py reddit-mask-spinrewriter.xlsx -c spinrewriter
        > reddit-search.py reddit-mask-wordai.xlsx -c wordai
        """,
    )

    # positional arguments
    arg_parser.add_argument(
        "file_name",
        nargs=1,
        metavar="FILE",
    )
    # optional arguments
    arg_parser.add_argument(
        "-r",
        "--recheck",
        action="store_true",
        default=False,
        help="recheck non-NULL values in 'found' column",
    )
    arg_parser.add_argument(
        "-c",
        "--column",
        default="original",
        help="sheet column to query [default: 'original']",
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
        help="Increase verbosity (specify multiple times for more)",
    )
    arg_parser.add_argument("--version", action="version", version="0.2")
    args = arg_parser.parse_args(argv)

    log_level = logging.ERROR  # 40

    if args.verbose == 1:
        log_level = logging.WARNING  # 30
    elif args.verbose == 2:
        log_level = logging.INFO  # 20
    elif args.verbose >= 3:
        log_level = logging.DEBUG  # 10
    LOG_FORMAT = "%(levelname).3s %(funcName).5s: %(message)s"
    if args.log_to_file:
        print("logging to file")
        logging.basicConfig(
            filename="reddit-search.log",
            filemode="w",
            level=log_level,
            format=LOG_FORMAT,
        )
    else:
        logging.basicConfig(level=log_level, format=LOG_FORMAT)

    return args


if __name__ == "__main__":
    args = main(sys.argv[1:])
    debug(f"{args=}")
    grab_quotes(args.file_name[0], args.column, args.recheck)
