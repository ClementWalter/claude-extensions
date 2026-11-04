#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Build index.html: one card per released Claude Desktop extension.

An extension is listed when a public, unarchived `<name>-cli` repo of OWNER has a
latest GitHub release carrying `<name>-cli.mcpb`. Its card comes from the repo's
`mcpb.json` on the default branch: `display_name`, `description`,
`long_description` (the setup steps) and the `site` block:

    "site": {
      "group": "home",                 # one of GROUPS
      "rank": 30,                       # order inside the group, low first
      "needs": ["A Matera account", "Signed in at app.matera.eu in Chrome"],
      "risk": "unofficial-api"          # a RISKS key, free text, or omitted
    }

A released extension without a valid `site` block fails the build with the
fix, so nothing ships to the page half-described. `--check` verifies that
index.html is up to date without writing it.
"""

from __future__ import annotations

import argparse
import html
import json
import logging
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

log = logging.getLogger("site")

OWNER = "ClementWalter"
ROOT = Path(__file__).resolve().parent
TEMPLATE = ROOT / "template.html"
OUTPUT = ROOT / "index.html"
API = "https://api.github.com"
UA = "claude-extensions-site"

# Page sections, in display order: id → heading.
GROUPS = {
    "messages": "Messages",
    "productivity": "Productivity",
    "press": "Press & reading",
    "home": "Home & family",
    "developer": "Developer",
}
_RISK_TAIL = "can change it at any time, which can break the extension until it is updated."
RISKS = {
    "unofficial-api": f"Reuses your website login and talks to the site's private, unofficial API, as you. The site {_RISK_TAIL}",
    "unofficial-apis": "Reuses your website logins and talks to the sites' private, unofficial APIs, as you. "
                       "They can change them at any time, which can break the extension until it is updated.",
}


class SiteError(Exception):
    """A released extension the page cannot describe; the message names the fix."""


# --------------------------------------------------------------------------- #
# GitHub
# --------------------------------------------------------------------------- #
def token() -> str | None:
    """GH_TOKEN/GITHUB_TOKEN, else the local `gh` login; unauthenticated is 60 calls/h."""
    for var in ("GH_TOKEN", "GITHUB_TOKEN"):
        if os.environ.get(var):
            return os.environ[var]
    try:
        out = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, timeout=10)
        return out.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def fetch(url: str, auth: str | None = None, accept: str = "application/vnd.github+json") -> bytes | None:
    """GET a URL; None on 404, raise on anything else unexpected."""
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": accept})
    if auth and url.startswith(API):
        req.add_header("Authorization", f"Bearer {auth}")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise


def released_extensions(auth: str | None) -> list[dict]:
    """[{repo, branch, manifest}] for every repo whose latest release ships `<repo>.mcpb`."""
    repos, page = [], 1
    while True:
        batch = json.loads(fetch(f"{API}/users/{OWNER}/repos?per_page=100&page={page}&type=owner", auth) or b"[]")
        repos += batch
        if len(batch) < 100:
            break
        page += 1
        if page > 20:
            raise SiteError("more than 2,000 repos listed; raise the page cap in build.py")
    out = []
    for repo in sorted(repos, key=lambda r: r["name"]):
        name = repo["name"]
        if not name.endswith("-cli") or repo.get("private") or repo.get("archived") or repo.get("fork"):
            continue
        release = fetch(f"{API}/repos/{OWNER}/{name}/releases/latest", auth)
        assets = {a["name"] for a in json.loads(release)["assets"]} if release else set()
        if f"{name}.mcpb" not in assets:
            continue
        # The contents API, not raw.githubusercontent.com, which caches for minutes.
        raw = fetch(f"{API}/repos/{OWNER}/{name}/contents/mcpb.json?ref={repo['default_branch']}",
                    auth, accept="application/vnd.github.raw")
        if raw is None:
            raise SiteError(f"{name}: its release ships {name}.mcpb but the repo has no mcpb.json")
        out.append({"repo": name, "manifest": json.loads(raw)})
    return out


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #
URL_RE = re.compile(r"https?://[^\s<>\"]+[^\s<>\".,;:!?)]")
CODE_RE = re.compile(r"`([^`]+)`")
STEP_RE = re.compile(r"^\d+\.\s+")


def inline(text: str) -> str:
    """Escape text, then turn `code` spans and bare URLs into markup."""
    out = html.escape(text, quote=False)
    out = CODE_RE.sub(lambda m: f"<code>{m.group(1)}</code>", out)
    return URL_RE.sub(lambda m: f'<a href="{m.group(0)}" rel="noopener">{m.group(0)}</a>', out)


def setup_html(long_description: str) -> str:
    """Paragraphs separated by blank lines; lines starting `1.` become an ordered list."""
    parts = []
    for para in re.split(r"\n\s*\n", long_description.strip()):
        lines = [ln.strip() for ln in para.splitlines() if ln.strip()]
        lead = [ln for ln in lines if not STEP_RE.match(ln)]
        steps = [STEP_RE.sub("", ln) for ln in lines if STEP_RE.match(ln)]
        if lead:
            parts.append(f"<p>{inline(' '.join(lead))}</p>")
        if steps:
            parts.append("<ol>" + "".join(f"<li>{inline(s)}</li>" for s in steps) + "</ol>")
    return "\n          ".join(parts)


def site_meta(repo: str, manifest: dict) -> dict:
    """Validate the `site` block; the error says exactly what to add."""
    site = manifest.get("site")
    example = '"site": {"group": "home", "rank": 50, "needs": ["…"], "risk": "unofficial-api"}'
    if not isinstance(site, dict):
        raise SiteError(f"{repo}: add a `site` block to mcpb.json, e.g. {example}")
    if site.get("group") not in GROUPS:
        raise SiteError(f"{repo}: mcpb.json site.group must be one of {', '.join(GROUPS)}")
    needs = site.get("needs")
    if not isinstance(needs, list) or not needs or not all(isinstance(n, str) and n for n in needs):
        raise SiteError(f"{repo}: mcpb.json site.needs must list what a user needs, e.g. [\"A Matera account\"]")
    for key in ("display_name", "description", "long_description"):
        if not manifest.get(key):
            raise SiteError(f"{repo}: mcpb.json needs `{key}`")
    return site


def card_html(repo: str, manifest: dict) -> str:
    site = site_meta(repo, manifest)
    risk = site.get("risk")
    risk = RISKS.get(risk, risk)
    download = f"https://github.com/{OWNER}/{repo}/releases/latest/download/{repo}.mcpb"
    lines = [
        f'      <article class="card" id="{repo.removesuffix("-cli")}">',
        f"        <h3>{html.escape(manifest['display_name'], quote=False)}</h3>",
        f'        <p class="desc">{inline(manifest["description"])}</p>',
        '        <p class="label">What you need</p>',
        '        <ul class="needs">' + "".join(f"<li>{inline(n)}</li>" for n in site["needs"]) + "</ul>",
    ]
    if risk:
        lines.append(f'        <p class="risk"><strong>Good to know.</strong> {inline(risk)}</p>')
    lines += [
        "        <details>",
        "          <summary>Setup steps</summary>",
        f"          {setup_html(manifest['long_description'])}",
        "        </details>",
        '        <p class="actions">',
        f'          <a class="button" href="{download}" download>Download</a>',
        f'          <a class="source" href="https://github.com/{OWNER}/{repo}" rel="noopener">Source code</a>',
        "        </p>",
        "      </article>",
    ]
    return "\n".join(lines)


def page_html(extensions: list[dict], template: str) -> str:
    """Fill the template's {{nav}} and {{groups}}; empty groups are left out."""
    by_group: dict[str, list[dict]] = {g: [] for g in GROUPS}
    for ext in extensions:
        by_group[site_meta(ext["repo"], ext["manifest"])["group"]].append(ext)
    sections, nav = [], []
    for gid, title in GROUPS.items():
        exts = sorted(by_group[gid], key=lambda e: (e["manifest"]["site"].get("rank", 100),
                                                    e["manifest"]["display_name"].lower()))
        if not exts:
            continue
        nav.append(f'<a href="#{gid}">{html.escape(title)}</a>')
        cards = "\n".join(card_html(e["repo"], e["manifest"]) for e in exts)
        sections.append(
            f'    <section class="group" id="{gid}">\n      <h2>{html.escape(title)}</h2>\n'
            f'      <div class="grid">\n{cards}\n      </div>\n    </section>'
        )
    nav.append('<a href="privacy/">Privacy</a>')
    return template.replace("{{nav}}", "".join(nav)).replace("{{groups}}", "\n".join(sections))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="Exit 1 if index.html is stale; write nothing.")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stderr)
    try:
        exts = released_extensions(token())
        page = page_html(exts, TEMPLATE.read_text())
    except SiteError as e:
        log.error("%s", e)
        return 1
    log.info("%d extensions: %s", len(exts), ", ".join(e["repo"] for e in exts))
    if OUTPUT.read_text() == page:
        log.info("index.html is up to date.")
        return 0
    if args.check:
        log.error("index.html is stale; run `uv run --script build.py`.")
        return 1
    OUTPUT.write_text(page)
    log.info("index.html rewritten.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
