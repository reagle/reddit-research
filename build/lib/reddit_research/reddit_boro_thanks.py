#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.13"
# dependencies = ["pandas", "pyarrow", "tqdm"]
# ///
"""Calculate percent of extant BORU submissions containing thanks.

Search selftext of non-deleted/removed submissions in r/BestofRedditorUpdates and r/BORUpdates through 2025-12-31 for \\bthank.
Exclude narrative and non-social variants (thanked, thanking, thankful, thankfully, thanksgiving, thank god/goodness/heaven/the lord).
Remove lines containing 'u/' to filter BORU compiler thanks to other BORU members.
~95% precision against manual review.
"""

import argparse
import re
import textwrap
from pathlib import Path

import pandas as pd
from tqdm import tqdm

PARQUET_FILES = [
    "BestofRedditorUpdates_submissions.parquet",
    "BORUpdates_submissions.parquet",
]
CUTOFF = pd.Timestamp("2025-12-31", tz="UTC")
THANK_PATTERN = re.compile(r"\bthank", re.IGNORECASE)
EXCLUDE_PATTERN = re.compile(
    r"\b(?:thanked|thanking|thankful|thankfully|thanksgiving"
    r"|thank\s+(?:god|goodness|heaven|the\s+lord))\b",
    re.IGNORECASE,
)


def _strip_excluded(text: str) -> str:
    """Remove excluded thank variants and lines containing u/ (compiler credits)."""
    cleaned = EXCLUDE_PATTERN.sub("", text)
    # Strip markdown bold/italic so u/ references aren't hidden
    stripped = re.sub(r"\*{1,2}", "", cleaned)
    # Remove lines containing u/ (compiler credits, not OOP thanks)
    lines = [line for line in stripped.splitlines() if "u/" not in line]
    return "\n".join(lines)


def load_submissions(data_dir: Path) -> pd.DataFrame:
    """Load and concatenate parquet files."""
    frames = [pd.read_parquet(data_dir / f) for f in PARQUET_FILES]
    return pd.concat(frames, ignore_index=True)


def filter_extant(df: pd.DataFrame) -> pd.DataFrame:
    """Keep non-deleted, non-removed submissions up to cutoff."""
    df["created_utc"] = pd.to_datetime(df["created_utc"], unit="s", utc=True)
    df = df[df["created_utc"] <= CUTOFF].copy()
    removed = {"[deleted]", "[removed]"}
    mask = (
        ~df["selftext"].isin(removed)
        & ~df["author"].isin(removed)
        & df["selftext"].notna()
        & (df["selftext"].str.strip() != "")
    )
    return df[mask]


def contains_thanks(text: str) -> bool:
    """Check for \\bthank excluding non-social, narrative, and compiler uses.

    >>> contains_thanks("Thank you for reading")
    True
    >>> contains_thanks("She thanked him profusely")
    False
    >>> contains_thanks("Thankfully it worked out")
    False
    >>> contains_thanks("Thank god it's over")
    False
    >>> contains_thanks("I'm so thankful for my sister")
    False
    >>> contains_thanks("We arrived for Thanksgiving dinner")
    False
    >>> contains_thanks("Thanks to u/bob for suggesting this")
    False
    >>> contains_thanks("**Thanks to** u/bob **for finding the BORU**")
    False
    >>> contains_thanks("Thanks for the updates")
    True
    """
    if not THANK_PATTERN.search(text):
        return False
    return bool(THANK_PATTERN.search(_strip_excluded(text)))


def extract_thank_context(text: str, width: int = 120) -> list[str]:
    """Return surrounding context for each thank match after exclusions."""
    cleaned = _strip_excluded(text)
    contexts = []
    for m in THANK_PATTERN.finditer(cleaned):
        start = max(0, m.start() - 60)
        end = min(len(cleaned), m.end() + 60)
        snippet = cleaned[start:end].replace("\n", " ").strip()
        contexts.append(f"...{snippet}...")
    return contexts


def print_sample(thanks_df: pd.DataFrame, n_sample: int) -> None:
    """Print evenly spaced sample of matching submissions with context."""
    n_matches = len(thanks_df)
    if n_matches == 0:
        print("No matches to sample.")
        return
    n_sample = min(n_sample, n_matches)
    step = n_matches / n_sample
    indices = [int(i * step) for i in range(n_sample)]
    sampled = thanks_df.iloc[indices]

    for i, (_, row) in enumerate(sampled.iterrows(), 1):
        date = row["created_utc"].strftime("%Y-%m-%d")
        title = textwrap.shorten(row.get("title", ""), width=80, placeholder="...")
        contexts = extract_thank_context(row["selftext"])
        print(f"\n{'=' * 80}")
        print(f"[{i}/{n_sample}] {date} | {title}")
        print(f"  https://reddit.com{row.get('permalink', '')}")
        for ctx in contexts[:3]:
            print(f"  >> {ctx}")


def process_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Calculate percent of BORU submissions containing thanks."
    )
    parser.add_argument(
        "-s",
        "--sample",
        type=int,
        default=0,
        metavar="N",
        help="print N evenly spaced examples of matching posts",
    )
    parser.add_argument(
        "-d",
        "--data-dir",
        type=Path,
        default=Path("."),
        help="directory containing parquet files (default: .)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = process_args(argv)
    df = load_submissions(args.data_dir)
    extant = filter_extant(df)

    tqdm.pandas(desc="Checking for thanks")
    extant = extant.copy()
    extant["has_thanks"] = extant["selftext"].progress_apply(contains_thanks)

    n_thanks = extant["has_thanks"].sum()
    n_total = len(extant)
    pct = n_thanks / n_total * 100

    print(f"Extant submissions: {n_total:,}")
    print(f"Containing thanks:  {n_thanks:,}")
    print(f"Percent:            {pct:.1f}%")

    if args.sample > 0:
        thanks_df = extant[extant["has_thanks"]].sort_values("created_utc")
        print_sample(thanks_df, args.sample)


if __name__ == "__main__":
    main()
