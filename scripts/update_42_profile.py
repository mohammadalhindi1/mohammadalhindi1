#!/usr/bin/env python3
"""Generate the 42 profile card and README project table.

Manual mode reads data/42-profile.json. Live mode retrieves public profile and
project data from the official 42 API using client-credentials stored in the
FT_API_UID and FT_API_SECRET environment variables.
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "42-profile.json"
SVG_PATH = ROOT / "assets" / "42-profile.svg"
README_PATH = ROOT / "README.md"
START_MARKER = "<!-- 42_PROJECTS:START -->"
END_MARKER = "<!-- 42_PROJECTS:END -->"


PROJECT_META = {
    "libft": (
        "A foundational C library covering memory, strings, lists, and reusable utilities.",
        "https://github.com/mohammadalhindi1/Libft",
    ),
    "ftprintf": (
        "Variadic functions, formatted output, parsing, and conversion handling.",
        "https://github.com/mohammadalhindi1/ft_printf",
    ),
    "getnextline": (
        "Buffered file-descriptor reading, static state, and careful memory management.",
        "https://github.com/mohammadalhindi1/git_next_line",
    ),
    "born2beroot": (
        "Linux administration, virtualization, LVM, SSH, security policies, and monitoring.",
        "https://github.com/mohammadalhindi1/Born2beRoot",
    ),
    "pushswap": (
        "Stack sorting algorithms, operation constraints, and move-count optimization.",
        "https://github.com/mohammadalhindi1/push-swap",
    ),
    "solong": (
        "2D graphics, event handling, map parsing, validation, and MiniLibX.",
        "https://github.com/mohammadalhindi1/so_long",
    ),
    "pipex": (
        "Process creation, pipes, file descriptors, redirection, and execve.",
        "https://github.com/mohammadalhindi1/Pipex",
    ),
    "minishell": (
        "UNIX processes, parsing, pipes, redirections, signals, and environment expansion.",
        "https://github.com/mohammadalhindi1/Minishell",
    ),
    "philosophers": (
        "POSIX threads, mutexes, synchronization, timing, and deadlock prevention.",
        "https://github.com/mohammadalhindi1/Philosophers",
    ),
    "netpractice": (
        "IPv4 addressing, subnetting, routing tables, gateways, and network troubleshooting.",
        "https://github.com/mohammadalhindi1/Net_Practice",
    ),
    "cub3d": (
        "Raycasting, map parsing, textures, movement, and real-time rendering in C.",
        "https://github.com/mohammadalhindi1/cub3D",
    ),
    "cppmodule": (
        "Object-oriented C++, canonical classes, inheritance, polymorphism, and templates.",
        "https://github.com/mohammadalhindi1/CPP-Module-0to4",
    ),
}


def api_request(url: str, token: str) -> Any:
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "User-Agent": "mohammadalhindi1-profile-readme",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def get_access_token(uid: str, secret: str) -> str:
    payload = urllib.parse.urlencode(
        {
            "grant_type": "client_credentials",
            "client_id": uid,
            "client_secret": secret,
        }
    ).encode()
    request = urllib.request.Request(
        "https://api.intra.42.fr/oauth/token",
        data=payload,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "mohammadalhindi1-profile-readme/1.0",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)["access_token"]


def project_key(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def project_meta(name: str) -> tuple[str, str]:
    key = project_key(name)
    for candidate, metadata in PROJECT_META.items():
        if key == candidate or key.endswith(candidate) or key.startswith(candidate):
            return metadata
    return ("A validated project from the 42 Core Curriculum.", "")


def choose_cursus(user: dict[str, Any]) -> dict[str, Any]:
    cursus_users = user.get("cursus_users") or []
    for entry in cursus_users:
        cursus = entry.get("cursus") or {}
        if cursus.get("slug") == "42cursus" or cursus.get("name") == "42cursus":
            return entry
    active = [entry for entry in cursus_users if entry.get("end_at") is None]
    if active:
        return active[-1]
    if cursus_users:
        return cursus_users[-1]
    raise RuntimeError("No cursus data returned by the 42 API")


def fetch_projects(user_id: int, token: str) -> list[dict[str, Any]]:
    projects: list[dict[str, Any]] = []
    page = 1
    while True:
        query = urllib.parse.urlencode({"page[number]": page, "page[size]": 100})
        batch = api_request(
            f"https://api.intra.42.fr/v2/users/{user_id}/projects_users?{query}", token
        )
        projects.extend(batch)
        if len(batch) < 100:
            return projects
        page += 1


def live_profile() -> dict[str, Any]:
    uid = os.environ.get("FT_API_UID", "").strip()
    secret = os.environ.get("FT_API_SECRET", "").strip()
    login = os.environ.get("FT_LOGIN", "malhendi").strip()
    if not uid or not secret:
        raise RuntimeError("FT_API_UID and FT_API_SECRET are required for live mode")

    token = get_access_token(uid, secret)
    user = api_request(f"https://api.intra.42.fr/v2/users/{login}", token)
    cursus_user = choose_cursus(user)
    cursus = cursus_user.get("cursus") or {}
    cursus_id = cursus.get("id")
    project_records = fetch_projects(user["id"], token)
    if cursus_id is not None:
        project_records = [
            item for item in project_records if cursus_id in (item.get("cursus_ids") or [])
        ]

    unique: dict[str, dict[str, Any]] = {}
    for item in project_records:
        project = item.get("project") or {}
        identity = str(project.get("id") or project.get("slug") or project.get("name"))
        previous = unique.get(identity)
        item_rank = (
            item.get("validated?") is True,
            item.get("marked_at") or item.get("updated_at") or "",
        )
        previous_rank = (
            previous.get("validated?") is True,
            previous.get("marked_at") or previous.get("updated_at") or "",
        ) if previous else (False, "")
        if previous is None or item_rank > previous_rank:
            unique[identity] = item

    completed: list[dict[str, Any]] = []
    current: list[dict[str, Any]] = []
    for item in unique.values():
        project = item.get("project") or {}
        name = project.get("name") or project.get("slug") or "42 Project"
        if item.get("validated?") is True and item.get("final_mark") is not None:
            description, repository = project_meta(name)
            completed.append(
                {
                    "name": name,
                    "score": item.get("final_mark"),
                    "completed_at": item.get("marked_at") or item.get("updated_at") or "",
                    "validated": True,
                    "description": description,
                    "repository": repository,
                }
            )
        elif item.get("status") in {
            "in_progress",
            "waiting_for_correction",
            "searching_a_group",
            "creating_group",
        }:
            current.append(item)

    completed.sort(key=lambda item: item.get("completed_at") or "", reverse=True)
    current.sort(key=lambda item: item.get("updated_at") or "", reverse=True)
    campus = (user.get("campus") or [{}])[0].get("name") or "42 Network"
    display_name = os.environ.get("FT_DISPLAY_NAME", "").strip()
    if not display_name:
        display_name = user.get("usual_full_name") or user.get("displayname") or login

    return {
        "display_name": display_name,
        "login": login,
        "campus": campus,
        "cursus": cursus.get("name") or cursus.get("slug") or "42cursus",
        "grade": cursus_user.get("grade") or "Cadet",
        "level": float(cursus_user.get("level") or 0),
        "current_projects": [
            (item.get("project") or {}).get("name") or "42 Project" for item in current[:2]
        ],
        "projects": completed,
    }


def load_manual_profile() -> dict[str, Any]:
    return json.loads(DATA_PATH.read_text(encoding="utf-8"))


def save_profile(data: dict[str, Any]) -> None:
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    DATA_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def clipped(value: Any, limit: int) -> str:
    text = str(value or "")
    return text if len(text) <= limit else text[: limit - 1] + "…"


def render_svg(data: dict[str, Any]) -> str:
    level = float(data.get("level") or 0)
    whole_level = int(level)
    progress = max(0, min(100, round((level - whole_level) * 100)))
    completed = [item for item in data.get("projects", []) if item.get("validated")]
    latest = completed[0] if completed else {}
    current_names = data.get("current_projects") or []
    current = " · ".join(current_names) if current_names else "Core Curriculum"
    progress_width = round(812 * progress / 100, 1)
    level_text = f"{level:.2f}"
    latest_name = clipped(latest.get("name") or "No project yet", 18)
    latest_score = latest.get("score")
    latest_value = f"{latest_name} · {latest_score}" if latest_score is not None else latest_name

    esc = lambda value: html.escape(str(value), quote=True)
    marker = ""
    if progress_width > 0:
        marker_x = 44 + progress_width
        marker = f'''<circle cx="{marker_x}" cy="217" r="5" fill="#e6edf3" filter="url(#glow)">
      <animate attributeName="opacity" values="1;.35;1" dur="1.8s" repeatCount="indefinite" />
    </circle>'''

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="900" height="260" viewBox="0 0 900 260" role="img" aria-labelledby="title description">
  <title id="title">Mohammad Alhindi's 42 Amman progress</title>
  <desc id="description">Level {level_text}, {progress} percent toward level {whole_level + 1}, with {len(completed)} validated projects.</desc>
  <defs>
    <linearGradient id="border" x1="0" y1="0" x2="900" y2="260" gradientUnits="userSpaceOnUse">
      <stop offset="0" stop-color="#22d3ee" />
      <stop offset=".52" stop-color="#2563eb" />
      <stop offset="1" stop-color="#8b5cf6" />
    </linearGradient>
    <linearGradient id="progress" x1="44" y1="0" x2="856" y2="0" gradientUnits="userSpaceOnUse">
      <stop offset="0" stop-color="#06b6d4" />
      <stop offset=".55" stop-color="#3b82f6" />
      <stop offset="1" stop-color="#8b5cf6" />
    </linearGradient>
    <radialGradient id="surface" cx="20%" cy="0%" r="105%">
      <stop offset="0" stop-color="#102a43" />
      <stop offset=".55" stop-color="#0d1b2a" />
      <stop offset="1" stop-color="#0d1117" />
    </radialGradient>
    <filter id="glow" x="-100%" y="-100%" width="300%" height="300%">
      <feGaussianBlur stdDeviation="3" result="blur" />
      <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
    </filter>
    <clipPath id="card"><rect x="1" y="1" width="898" height="258" rx="24" /></clipPath>
  </defs>

  <rect x="1" y="1" width="898" height="258" rx="24" fill="url(#surface)" stroke="url(#border)" stroke-width="2" />
  <g clip-path="url(#card)" opacity=".55">
    <path d="M-20 34 H215 L248 1 M650 1 L690 41 H930" fill="none" stroke="#164e63" />
    <path d="M-10 246 H245 L266 225 H645 L666 246 H920" fill="none" stroke="#312e81" />
  </g>

  <g font-family="Inter, Segoe UI, Arial, sans-serif">
    <g transform="translate(44 29)">
      <rect width="58" height="58" rx="16" fill="#111827" stroke="#22d3ee" stroke-width="1.5" />
      <text x="29" y="38" fill="#e6edf3" font-size="27" font-weight="800" text-anchor="middle">42</text>
      <circle cx="52" cy="7" r="3" fill="#22d3ee"><animate attributeName="opacity" values=".3;1;.3" dur="2s" repeatCount="indefinite" /></circle>
    </g>

    <text x="120" y="43" fill="#8b949e" font-size="11" font-weight="700" letter-spacing="2">42 AMMAN / CORE CURRICULUM</text>
    <text x="120" y="69" fill="#e6edf3" font-size="24" font-weight="750">{esc(data.get("display_name") or "Mohammad Alhindi")}</text>
    <text x="120" y="90" fill="#38bdf8" font-size="13" font-weight="600">@{esc(data.get("login") or "malhendi")}  ·  {esc(data.get("campus") or "42 Amman")}</text>
    <text x="856" y="43" fill="#7dd3fc" font-size="11" font-weight="700" text-anchor="end" letter-spacing="1.2">{esc(str(data.get("cursus") or "42cursus").upper())} · {esc(str(data.get("grade") or "Cadet").upper())}</text>

    <g transform="translate(44 112)">
      <rect width="170" height="62" rx="14" fill="#111827" stroke="#263449" />
      <text x="16" y="22" fill="#8b949e" font-size="10" font-weight="700" letter-spacing="1.3">LEVEL</text>
      <text x="16" y="49" fill="#22d3ee" font-size="24" font-weight="800">{level_text}</text>
    </g>
    <g transform="translate(230 112)">
      <rect width="190" height="62" rx="14" fill="#111827" stroke="#263449" />
      <text x="16" y="22" fill="#8b949e" font-size="10" font-weight="700" letter-spacing="1.3">VALIDATED</text>
      <text x="16" y="48" fill="#e6edf3" font-size="18" font-weight="750">{len(completed)} projects</text>
    </g>
    <g transform="translate(436 112)">
      <rect width="220" height="62" rx="14" fill="#111827" stroke="#263449" />
      <text x="16" y="22" fill="#8b949e" font-size="10" font-weight="700" letter-spacing="1.3">CURRENT</text>
      <text x="16" y="48" fill="#e6edf3" font-size="17" font-weight="750">{esc(clipped(current, 21))}</text>
    </g>
    <g transform="translate(672 112)">
      <rect width="184" height="62" rx="14" fill="#111827" stroke="#263449" />
      <text x="16" y="22" fill="#8b949e" font-size="10" font-weight="700" letter-spacing="1.3">LATEST</text>
      <text x="16" y="48" fill="#e6edf3" font-size="15" font-weight="750">{esc(clipped(latest_value, 20))}</text>
    </g>

    <text x="44" y="199" fill="#c9d1d9" font-size="12" font-weight="650">Level {whole_level} · {progress}% toward Level {whole_level + 1}</text>
    <text x="856" y="199" fill="#8b949e" font-size="11" text-anchor="end">Updates when 42 data changes</text>
    <rect x="44" y="208" width="812" height="18" rx="9" fill="#334155" />
    <rect x="44" y="208" width="{progress_width}" height="18" rx="9" fill="url(#progress)">
      <animate attributeName="opacity" values=".82;1;.82" dur="2.4s" repeatCount="indefinite" />
    </rect>
    {marker}
    <text x="44" y="246" fill="#64748b" font-size="10" letter-spacing="1">PUBLIC 42 PROFILE DATA</text>
    <text x="856" y="246" fill="#64748b" font-size="10" text-anchor="end" letter-spacing="1">GENERATED FOR GITHUB</text>
  </g>
</svg>
'''


def project_markdown(data: dict[str, Any]) -> str:
    projects = [item for item in data.get("projects", []) if item.get("validated")]
    projects.sort(key=lambda item: item.get("completed_at") or "", reverse=True)
    current = " · ".join(data.get("current_projects") or []) or "Core Curriculum"
    lines = [
        f"**Current project:** {current}  ",
        f"**Validated projects:** {len(projects)}",
        "",
        "| Project | Score | What it demonstrates |",
        "|---|:---:|---|",
    ]
    for item in projects:
        name = str(item.get("name") or "42 Project")
        repository = str(item.get("repository") or "")
        label = f"[{name}]({repository})" if repository else name
        score = item.get("score")
        score_text = f"**{score}**" if score is not None else "Validated"
        description = str(item.get("description") or "A validated 42 Core Curriculum project.")
        lines.append(f"| {label} | {score_text} | {description} |")
    return "\n".join(lines)


def update_readme(data: dict[str, Any]) -> None:
    if not README_PATH.exists():
        raise RuntimeError(f"README not found at {README_PATH}")
    readme = README_PATH.read_text(encoding="utf-8")
    if START_MARKER not in readme or END_MARKER not in readme:
        raise RuntimeError("42 README markers are missing")
    replacement = f"{START_MARKER}\n{project_markdown(data)}\n{END_MARKER}"
    pattern = re.compile(re.escape(START_MARKER) + r".*?" + re.escape(END_MARKER), re.DOTALL)
    README_PATH.write_text(pattern.sub(replacement, readme), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--live", action="store_true", help="Fetch current data from the 42 API")
    mode.add_argument("--manual", action="store_true", help="Read data/42-profile.json")
    parser.add_argument("--skip-readme", action="store_true", help="Generate only JSON/SVG")
    args = parser.parse_args()

    data = live_profile() if args.live else load_manual_profile()
    if args.live:
        save_profile(data)
    SVG_PATH.parent.mkdir(parents=True, exist_ok=True)
    SVG_PATH.write_text(render_svg(data), encoding="utf-8")
    if not args.skip_readme:
        update_readme(data)


if __name__ == "__main__":
    main()
