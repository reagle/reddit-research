#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.13"
# dependencies = ["pandas", "pyarrow", "tqdm"]
# ///
"""Generate demographic statistics table from Reddit submission parquet files."""

import argparse
import re
from pathlib import Path

import pandas as pd
from tqdm import tqdm

PATTERN = re.compile(r"(I|My) ?[(\[](\d\d)([FM])[)\]]", re.IGNORECASE)
SUBREDDITS = [
    "relationship_advice",
    "legaladvice",
    "AmItheAsshole",
    "personalfinance",
    "AskDocs",
    "offmychest",
]


def extract_demographics(text: str) -> tuple[int, str] | None:
    """Extract age and gender from post text.

    >>> extract_demographics("I (26F) am having trouble")
    (26, 'F')
    >>> extract_demographics("My [32M] girlfriend")
    (32, 'M')
    >>> extract_demographics("I(19f) need advice")
    (19, 'F')
    >>> extract_demographics("No demographics here")
    >>> extract_demographics(None)
    """
    if not isinstance(text, str):
        return None
    if match := PATTERN.search(text):
        age = int(match.group(2))
        gender = match.group(3).upper()
        return (age, gender)
    return None


def format_count(n: int) -> str:
    """Format count with K/M suffix.

    >>> format_count(500)
    '500'
    >>> format_count(1500)
    '1.5K'
    >>> format_count(12000)
    '12.0K'
    >>> format_count(1500000)
    '1.5M'
    """
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def process_subreddit(
    parquet_path: Path, start_year: int, end_year: int, verbose: bool = False
) -> dict | None:
    """Process a single subreddit's parquet file."""
    sub_name = parquet_path.stem.replace("_submissions", "")

    if verbose:
        print(f"\n  Loading {parquet_path.name}...", end=" ", flush=True)
    df = pd.read_parquet(parquet_path)
    if verbose:
        print(f"{len(df):,} rows")

    # Filter by year using created_utc
    df["year"] = pd.to_datetime(df["created_utc"], unit="s").dt.year
    df = df[(df["year"] >= start_year) & (df["year"] <= end_year)]
    if verbose:
        print(f"  Filtered to {start_year}--{end_year}: {len(df):,} rows")

    # Try selftext first, fall back to title
    text_col = "selftext" if "selftext" in df.columns else "title"
    if verbose:
        print(f"  Extracting demographics from '{text_col}'...")
        texts = df[text_col].tolist()
        df["demo"] = [
            extract_demographics(t)
            for t in tqdm(texts, desc=f"  {sub_name}", leave=False)
        ]
    else:
        df["demo"] = df[text_col].apply(extract_demographics)
    matched = df.dropna(subset=["demo"])

    if verbose:
        print(
            f"  Matched: {len(matched):,} / {len(df):,} ({100 * len(matched) / len(df):.1f}%)"
        )

    if matched.empty:
        return None

    matched = matched.copy()
    matched[["age", "gender"]] = pd.DataFrame(
        matched["demo"].tolist(), index=matched.index
    )

    # Filter reasonable ages
    pre_filter = len(matched)
    matched = matched[(matched["age"] >= 13) & (matched["age"] <= 80)]
    if verbose and pre_filter != len(matched):
        print(f"  Filtered invalid ages: {pre_filter:,} -> {len(matched):,}")

    n = len(matched)
    age_20 = int(matched["age"].quantile(0.20))
    age_80 = int(matched["age"].quantile(0.80))
    pct_female = matched["gender"].eq("F").mean() * 100
    pct_male = 100 - pct_female

    return {
        "subreddit": sub_name,
        "age": f"{age_20}--{age_80}",
        "% female": round(pct_female),
        "% male": round(pct_male),
        "messages matched": format_count(n),
    }


def process_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Generate Reddit demographic stats table"
    )
    parser.add_argument(
        "data_dir",
        type=Path,
        help="Directory containing parquet files",
    )
    parser.add_argument(
        "--start-year",
        type=int,
        default=2020,
        help="Start year (default: 2020)",
    )
    parser.add_argument(
        "--end-year",
        type=int,
        default=2024,
        help="End year (default: 2024)",
    )
    parser.add_argument(
        "--subreddits",
        nargs="+",
        default=SUBREDDITS,
        help="Subreddits to process (default: predefined list)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show detailed diagnostics",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """Generate demographic statistics table."""
    args = process_args(argv)

    if args.verbose:
        print(
            f"Processing {len(args.subreddits)} subreddits for {args.start_year}--{args.end_year}"
        )

    results = []
    subreddit_iter = (
        tqdm(args.subreddits, desc="Subreddits")
        if not args.verbose
        else args.subreddits
    )

    for sub in subreddit_iter:
        parquet_path = args.data_dir / f"{sub}_submissions.parquet"
        if not parquet_path.exists():
            print(f"Warning: {parquet_path} not found, skipping")
            continue
        if stats := process_subreddit(
            parquet_path, args.start_year, args.end_year, args.verbose
        ):
            results.append(stats)

    if not results:
        print("No data found")
        return

    # Output as markdown table
    print()
    df = pd.DataFrame(results)
    print(df.to_markdown(index=False))
    print()
    print(
        f"Table: [Table 4.1: {args.start_year}--{args.end_year} poster demographics]{{#tbl_4_1_gender_age}}; age is the 20th--80th percentiles"
    )


if __name__ == "__main__":
    main()
