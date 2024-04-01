#!/usr/bin/env python3
"""Plot subreddits creation and relative size.
"""

__author__ = "Joseph Reagle"
__copyright__ = "Copyright (C) 2024 Joseph Reagle"
__license__ = "GLPv3"
__version__ = "0.1"


import argparse
import os

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# Create an argument parser
parser = argparse.ArgumentParser(
    description="Plot subreddits creation and relative size."
)
parser.add_argument("-i", "--input", required=True, help="Path to the input CSV file")
args = parser.parse_args()

# Read in the CSV data
df = pd.read_csv(args.input)

# Convert the 'creation' column to datetime
df["creation"] = pd.to_datetime(df["creation"], format="%Y-%m-%d")

# Sort by date
df = df.sort_values("creation")

# Calculate the relative size of each subreddit
df["Relative Size"] = df["subscribers"] / df["subscribers"].max() * 1000

# Create a dictionary to map categories to colors
category_colors = {
    "general": "blue",
    "funny": "orange",
    "judgement": "green",
    "health": "red",
    "gender": "purple",
    "relationship": "brown",
}

# Set the threshold values
THRESHOLD_SIZE = 10000  # Ignore subreddits with subscribers less than this value
THRESHOLD_YEAR = 2016  # Ignore subreddits created after this year

# Create the plot
fig, ax = plt.subplots(figsize=(12, 8))
ADJUST_CIRCUMFERENCE = 7
ADJUST_CIRCLE_LABEL_OFFSET = 10

# Create a dictionary to store the legend handles and labels
legend_handles = {}
legend_labels = {}

# Plot each subreddit as a circle with color based on category
for _, row in df.iterrows():
    if row["subscribers"] < THRESHOLD_SIZE or row["creation"].year > THRESHOLD_YEAR:
        continue  # Skip subreddits that don't meet the threshold criteria

    category = row["category"]
    color = category_colors.get(category, "gray")  # Default color if category not found

    # Add the category to the legend handles and labels if not already present
    if category not in legend_handles:
        legend_handles[category] = plt.Line2D(
            [], [], color=color, marker="o", linestyle="None", markersize=8
        )
        legend_labels[category] = category

    circle = ax.scatter(
        row["creation"],
        row["subscribers"],
        s=row["Relative Size"] * ADJUST_CIRCUMFERENCE,
        alpha=0.7,
        color=color,
    )
    radius = circle.get_sizes()[0] / 2
    if radius > 0:
        shift = pd.Timedelta(days=np.log(radius) * ADJUST_CIRCLE_LABEL_OFFSET)
    else:
        shift = pd.Timedelta(days=0)  # Set shift to 0 if radius is 0 or very small
    ax.text(
        row["creation"] + shift,
        row["subscribers"],
        row["subreddit"],
        fontsize=8,
        va="center",
        bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.7, "pad": 2},
    )

# Format the x-axis as dates
ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
ax.xaxis.set_major_locator(mdates.YearLocator())
fig.autofmt_xdate()

# Set the y-axis to logarithmic scale
ax.set_yscale("log")

# Adjust x-axis limits to provide extra space on the right side
x_min, x_max = ax.get_xlim()
x_max_date = mdates.num2date(x_max)  # Convert x_max to datetime
ax.set_xlim(
    x_min, mdates.date2num(x_max_date + pd.Timedelta(days=365))
)  # Add one year of extra space

# Add labels
ax.set_xlabel("Date Created")
ax.set_ylabel("Number of Subscribers")
ax.set_title("Growth of Popular Subreddits")

# Add the legend to the plot
ax.legend(
    handles=legend_handles.values(), labels=legend_labels.values(), loc="upper right"
)

plt.tight_layout()

# Save the plot as a PNG file with the same name as the input file
output_file = os.path.splitext(args.input)[0] + ".png"
plt.savefig(output_file)

plt.show()
