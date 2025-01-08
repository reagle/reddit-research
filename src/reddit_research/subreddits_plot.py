#!/usr/bin/env python3
"""Plot subreddits creation and relative size."""

__author__ = "Joseph Reagle"
__copyright__ = "Copyright (C) 2024 Joseph Reagle"
__license__ = "GLPv3"
__version__ = "0.2"

import argparse
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.patheffects as path_effects
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from adjustText import adjust_text


def process_args():
    """Process command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Plot subreddits creation and relative size."
    )
    parser.add_argument(
        "-i", "--input", type=Path, required=True, help="Path to the input CSV file"
    )
    return parser.parse_args()


def main():
    """Main entry point of the script."""
    args = process_args()

    # Read in the CSV data
    df = pd.read_csv(args.input, comment="#")

    # Convert the 'subscribers' column to numeric, replacing non-numeric values with NaN
    df["subscribers"] = pd.to_numeric(df["subscribers"], errors="coerce")

    # Convert the 'created' column to datetime
    df["created"] = pd.to_datetime(df["created"], format="%Y-%m-%d")

    # Sort by date
    df = df.sort_values("created")

    # Calculate the relative size of each subreddit
    ADJUST_CIRCUMFERENCE = 4  # Adjustable parameter for bubble size
    df["relative_size"] = df["subscribers"] / df["subscribers"].max() * 1000

    # Create a dictionary to map categories to colors
    category_colors = {
        "general": "magenta",
        "relationship": "blue",
        "legal": "teal",
        "finance": "olive",
        "health": "red",
        "fashion": "pink",
        "gender": "green",
        "disclosure": "purple",
        "judgement": "orange",
    }

    # Set the threshold values
    THRESHOLD_SIZE = 10000  # Ignore subreddits with subscribers less than this value
    THRESHOLD_YEAR = 2024  # Ignore subreddits created after this year

    # Filter data based on thresholds
    df_filtered = df[
        (df["subscribers"] >= THRESHOLD_SIZE)
        & (df["created"].dt.year <= THRESHOLD_YEAR)
    ]

    BUBBLE_SCALE_FACTOR = 5  # Adjustable factor for overall bubble size

    # Create the plot using Seaborn
    plt.figure(figsize=(12, 8))
    sns.scatterplot(
        data=df_filtered,
        x="created",
        y="subscribers",
        size="relative_size",
        hue="category",
        palette=category_colors,
        sizes=(20 * BUBBLE_SCALE_FACTOR, 2000 * BUBBLE_SCALE_FACTOR),
        alpha=0.7,
        legend=False,
    )

    # Customize plot aesthetics
    plt.yscale("log")
    plt.xlabel("Date Created")
    plt.ylabel("Number of Subscribers")
    plt.title("Creation and Size of Advice Subreddits")

    # Create a custom legend for categories only
    legend_elements = [
        plt.Line2D(
            [0],
            [0],
            marker="o",
            color="w",
            label=cat,
            markerfacecolor=color,
            markersize=10,
        )
        for cat, color in category_colors.items()
    ]
    plt.legend(
        handles=legend_elements,
        title="Category",
        bbox_to_anchor=(1.05, 1),
        loc="upper left",
    )

    texts = []
    for _, row in df_filtered.iterrows():
        texts.append(
            plt.text(
                row["created"],
                row["subscribers"],
                row["subreddit"],
                fontsize=10,
                va="center",
                ha="left",
                path_effects=[path_effects.withStroke(linewidth=3, foreground="white")],
            )
        )

    # Adjust the positions of the labels
    adjust_text(texts, arrowprops={"arrowstyle": "-", "color": "k", "lw": 0.0})

    # Adjust x-axis limits to provide extra space on both sides
    x_min, x_max = plt.xlim()
    x_min_date = mdates.num2date(x_min)
    x_max_date = mdates.num2date(x_max)
    plt.xlim(
        mdates.date2num(x_min_date - pd.Timedelta(days=100)),
        mdates.date2num(x_max_date + pd.Timedelta(days=200)),
    )

    plt.tight_layout()

    # Save and show plot
    output_file = Path(args.input).with_suffix(".png")
    plt.savefig(output_file, dpi=300)
    plt.show()


if __name__ == "__main__":
    main()
