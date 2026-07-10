"""Render dark/light terminal profile SVGs from template.svg using live GitHub stats."""
import os
import re
import datetime
import requests
from dateutil.relativedelta import relativedelta

USERNAME = os.environ["USER_NAME"]
HEADERS = {"authorization": f"token {os.environ['ACCESS_TOKEN']}"}
GRAPHQL = "https://api.github.com/graphql"

PALETTES = {
    "dark_mode.svg": {
        "bg": "#1a1b27", "panel": "#24283b", "border": "#414868",
        "titlebar_fg": "#8188a5", "fg": "#c0caf5", "accent": "#bb9af7",
        "prompt": "#9ece6a", "path": "#7dcfff", "cmd": "#c0caf5",
        "key": "#7aa2f7", "str": "#9ece6a", "num": "#ff9e64", "punct": "#565f89",
        "caret": "#7dcfff", "dot_red": "#f7768e", "dot_yellow": "#e0af68", "dot_green": "#9ece6a",
    },
    "light_mode.svg": {
        "bg": "#e1e2e7", "panel": "#d5d6db", "border": "#b7bac9",
        "titlebar_fg": "#6c7086", "fg": "#3760bf", "accent": "#9854f1",
        "prompt": "#587539", "path": "#007197", "cmd": "#3760bf",
        "key": "#2e7de9", "str": "#587539", "num": "#b15c00", "punct": "#8990b3",
        "caret": "#007197", "dot_red": "#f52a65", "dot_yellow": "#8c6c3e", "dot_green": "#587539",
    },
}


def query(gql, variables):
    resp = requests.post(GRAPHQL, json={"query": gql, "variables": variables}, headers=HEADERS)
    resp.raise_for_status()
    data = resp.json()
    if "errors" in data:
        raise RuntimeError(data["errors"])
    return data["data"]


def overview():
    gql = """
    query($login: String!, $after: String) {
      user(login: $login) {
        createdAt
        followers { totalCount }
        repositories(first: 100, after: $after, ownerAffiliations: OWNER, isFork: false) {
          totalCount
          pageInfo { hasNextPage endCursor }
          nodes { stargazerCount }
        }
      }
    }"""
    stars, repos, created, followers, after = 0, 0, None, 0, None
    while True:
        user = query(gql, {"login": USERNAME, "after": after})["user"]
        created = user["createdAt"]
        followers = user["followers"]["totalCount"]
        page = user["repositories"]
        repos = page["totalCount"]
        stars += sum(n["stargazerCount"] for n in page["nodes"])
        if not page["pageInfo"]["hasNextPage"]:
            break
        after = page["pageInfo"]["endCursor"]
    return created, followers, repos, stars


def total_commits(created_at):
    gql = """
    query($login: String!, $from: DateTime!, $to: DateTime!) {
      user(login: $login) {
        contributionsCollection(from: $from, to: $to) {
          totalCommitContributions
          restrictedContributionsCount
        }
      }
    }"""
    start = datetime.datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%SZ")
    now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
    total = 0
    for year in range(start.year, now.year + 1):
        frm = max(start, datetime.datetime(year, 1, 1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        to = min(now, datetime.datetime(year, 12, 31, 23, 59, 59)).strftime("%Y-%m-%dT%H:%M:%SZ")
        contrib = query(gql, {"login": USERNAME, "from": frm, "to": to})["user"]["contributionsCollection"]
        total += contrib["totalCommitContributions"] + contrib["restrictedContributionsCount"]
    return total


def account_age(created_at):
    start = datetime.datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%SZ")
    delta = relativedelta(datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None), start)
    parts = []
    if delta.years:
        parts.append(f"{delta.years}y")
    if delta.months:
        parts.append(f"{delta.months}mo")
    parts.append(f"{delta.days}d")
    return " ".join(parts)


def render(template, mapping):
    return re.sub(r"\{\{(\w+)\}\}", lambda m: str(mapping[m.group(1)]), template)


def main():
    created, followers, repos, stars = overview()
    data = {
        "commits": f"{total_commits(created):,}",
        "stars": f"{stars:,}",
        "repos": f"{repos:,}",
        "followers": f"{followers:,}",
        "age": account_age(created),
    }
    with open("template.svg", encoding="utf-8") as f:
        template = f.read()
    for filename, palette in PALETTES.items():
        with open(filename, "w", encoding="utf-8") as f:
            f.write(render(template, {**palette, **data}))
    print("Generated:", ", ".join(PALETTES), "|", data)


if __name__ == "__main__":
    main()
