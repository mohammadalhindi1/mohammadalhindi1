#!/usr/bin/env python3
"""Generate a self-contained GitHub activity card for a profile README."""

from __future__ import annotations

import argparse
import html
import json
import os
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable


GITHUB_GRAPHQL_URL = "https://api.github.com/graphql"


@dataclass(frozen=True)
class ActivityStats:
    total: int
    current: int
    longest: int
    period_start: date
    period_end: date
    current_start: date | None
    current_end: date | None
    longest_start: date | None
    longest_end: date | None


def fetch_contribution_calendar(token: str, username: str) -> dict:
    query = """
    query($login: String!) {
      user(login: $login) {
        contributionsCollection {
          contributionCalendar {
            totalContributions
            weeks {
              contributionDays {
                date
                contributionCount
              }
            }
          }
        }
      }
    }
    """
    body = json.dumps({"query": query, "variables": {"login": username}}).encode()
    request = urllib.request.Request(
        GITHUB_GRAPHQL_URL,
        data=body,
        method="POST",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "github-profile-activity-card",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as error:
        details = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub API returned HTTP {error.code}: {details}") from error
    except urllib.error.URLError as error:
        raise RuntimeError(f"Could not reach GitHub API: {error.reason}") from error

    if payload.get("errors"):
        messages = "; ".join(item.get("message", "Unknown GraphQL error") for item in payload["errors"])
        raise RuntimeError(f"GitHub GraphQL error: {messages}")

    user = payload.get("data", {}).get("user")
    if user is None:
        raise RuntimeError(f"GitHub user '{username}' was not found")

    return user["contributionsCollection"]["contributionCalendar"]


def flatten_days(calendar: dict) -> list[tuple[date, int]]:
    days: list[tuple[date, int]] = []
    for week in calendar.get("weeks", []):
        for item in week.get("contributionDays", []):
            days.append((date.fromisoformat(item["date"]), int(item["contributionCount"])))
    return sorted(days)


def calculate_stats(days: Iterable[tuple[date, int]], total: int | None = None) -> ActivityStats:
    ordered = sorted(days)
    if not ordered:
        raise RuntimeError("GitHub returned an empty contribution calendar")

    counts = dict(ordered)
    period_start, period_end = ordered[0][0], ordered[-1][0]

    longest = 0
    longest_start: date | None = None
    longest_end: date | None = None
    running = 0
    running_start: date | None = None
    previous: date | None = None

    for day, count in ordered:
        if count > 0:
            if previous is None or day != previous + timedelta(days=1) or running == 0:
                running = 1
                running_start = day
            else:
                running += 1
            if running > longest:
                longest = running
                longest_start = running_start
                longest_end = day
        else:
            running = 0
            running_start = None
        previous = day

    today = min(datetime.now(timezone.utc).date(), period_end)
    cursor = today if counts.get(today, 0) > 0 else today - timedelta(days=1)
    current_end = cursor if counts.get(cursor, 0) > 0 else None
    current = 0
    while counts.get(cursor, 0) > 0:
        current += 1
        cursor -= timedelta(days=1)
    current_start = cursor + timedelta(days=1) if current else None

    return ActivityStats(
        total=int(total if total is not None else sum(counts.values())),
        current=current,
        longest=longest,
        period_start=period_start,
        period_end=period_end,
        current_start=current_start,
        current_end=current_end,
        longest_start=longest_start,
        longest_end=longest_end,
    )


def format_date(value: date | None) -> str:
    if value is None:
        return "—"
    return value.strftime("%b %d, %Y").replace(" 0", " ")


def format_range(start: date | None, end: date | None) -> str:
    if start is None or end is None:
        return "No active streak"
    if start == end:
        return format_date(start)
    return f"{format_date(start)} – {format_date(end)}"


def render_svg(username: str, stats: ActivityStats) -> str:
    safe_username = html.escape(username)
    total_range = f"{format_date(stats.period_start)} – {format_date(stats.period_end)}"
    current_range = format_range(stats.current_start, stats.current_end)
    longest_range = format_range(stats.longest_start, stats.longest_end)
    updated = datetime.now(timezone.utc).date().isoformat()

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="760" height="210" viewBox="0 0 760 210" role="img" aria-labelledby="title desc">
  <title id="title">GitHub activity for {safe_username}</title>
  <desc id="desc">{stats.total} contributions, {stats.current} day current streak, and {stats.longest} day longest streak.</desc>
  <style>
    .card {{ fill: #0D1117; stroke: #30363D; stroke-width: 1; }}
    .title {{ fill: #F0F6FC; font: 600 18px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
    .subtitle {{ fill: #8B949E; font: 12px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
    .number {{ fill: #38BDF8; font: 700 34px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
    .number-current {{ fill: #06B6D4; }}
    .label {{ fill: #C9D1D9; font: 600 13px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
    .range {{ fill: #8B949E; font: 11px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
    .divider {{ stroke: #21262D; stroke-width: 1; }}
  </style>
  <rect class="card" x="0.5" y="0.5" width="759" height="209" rx="12" />
  <circle cx="25" cy="28" r="6" fill="#38BDF8" />
  <text class="title" x="40" y="34">GitHub Activity</text>
  <text class="subtitle" x="735" y="33" text-anchor="end">Updated {updated} UTC</text>
  <line class="divider" x1="253" y1="61" x2="253" y2="177" />
  <line class="divider" x1="506" y1="61" x2="506" y2="177" />

  <g text-anchor="middle">
    <text class="number" x="127" y="111">{stats.total}</text>
    <text class="label" x="127" y="137">Total Contributions</text>
    <text class="range" x="127" y="158">{total_range}</text>

    <text class="number number-current" x="380" y="111">{stats.current}</text>
    <text class="label" x="380" y="137">Current Streak (days)</text>
    <text class="range" x="380" y="158">{current_range}</text>

    <text class="number" x="633" y="111">{stats.longest}</text>
    <text class="label" x="633" y="137">Longest Streak (days)</text>
    <text class="range" x="633" y="158">{longest_range}</text>
  </g>
</svg>
'''


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="assets/github-activity.svg", help="SVG output path")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    username = (os.environ.get("GITHUB_USERNAME") or os.environ.get("GITHUB_REPOSITORY_OWNER") or "").strip()
    if not token:
        print("GITHUB_TOKEN is required", file=sys.stderr)
        return 1
    if not username:
        print("GITHUB_USERNAME or GITHUB_REPOSITORY_OWNER is required", file=sys.stderr)
        return 1

    try:
        calendar = fetch_contribution_calendar(token, username)
        stats = calculate_stats(flatten_days(calendar), calendar.get("totalContributions"))
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(render_svg(username, stats), encoding="utf-8")
    except (KeyError, TypeError, ValueError, RuntimeError) as error:
        print(f"Failed to generate GitHub activity card: {error}", file=sys.stderr)
        return 1

    print(f"Wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
