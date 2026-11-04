#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pytest==9.1.1",
# ]
#
# [tool.uv]
# exclude-newer = "2026-10-27T00:00:00Z"
# ///
"""Offline tests for build.py: card rendering, site-block validation, page assembly."""

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def b():
    spec = importlib.util.spec_from_file_location("build", ROOT / "build.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def manifest(**site):
    return {
        "display_name": "Demo",
        "description": "Read a demo account from Claude.",
        "long_description": "Reads things.\n\nSetup:\n1. Sign in at https://demo.example.com.\n2. Ask Claude.",
        "site": {"group": "home", "needs": ["A demo account"], **site},
    }


@pytest.fixture
def template():
    return '<nav>{{nav}}</nav>\n{{groups}}\n'


def test_inline_escapes_html(b):
    assert b.inline("a < b & c") == "a &lt; b &amp; c"


def test_inline_links_url_without_trailing_dot(b):
    assert b.inline("see https://x.example.com.") == 'see <a href="https://x.example.com" rel="noopener">https://x.example.com</a>.'


def test_inline_code_span(b):
    assert b.inline("run `security`") == "run <code>security</code>"


def test_setup_html_turns_steps_into_list(b):
    assert "<ol><li>one</li><li>two</li></ol>" in b.setup_html("Setup:\n1. one\n2. two")


def test_setup_html_keeps_lead_paragraph(b):
    assert b.setup_html("Setup:\n1. one").startswith("<p>Setup:</p>")


def test_card_has_download_link(b):
    assert "releases/latest/download/demo-cli.mcpb" in b.card_html("demo-cli", manifest())


def test_card_id_drops_cli_suffix(b):
    assert 'id="demo"' in b.card_html("demo-cli", manifest())


def test_card_expands_risk_preset(b):
    assert "private, unofficial API" in b.card_html("demo-cli", manifest(risk="unofficial-api"))


def test_card_keeps_free_text_risk(b):
    assert "Custom warning." in b.card_html("demo-cli", manifest(risk="Custom warning."))


def test_card_without_risk_has_no_risk_line(b):
    assert 'class="risk"' not in b.card_html("demo-cli", manifest())


def test_missing_site_block_names_fix(b):
    m = manifest()
    del m["site"]
    with pytest.raises(b.SiteError, match="add a `site` block"):
        b.site_meta("demo-cli", m)


@pytest.mark.parametrize("site", [{"group": "nowhere", "needs": ["x"]}, {"group": "home", "needs": []}])
def test_invalid_site_block_rejected(b, site):
    m = manifest()
    m["site"] = site
    with pytest.raises(b.SiteError):
        b.site_meta("demo-cli", m)


def test_page_orders_cards_by_rank(b, template):
    exts = [{"repo": "late-cli", "manifest": manifest(rank=20)}, {"repo": "early-cli", "manifest": manifest(rank=10)}]
    page = b.page_html(exts, template)
    assert page.index('id="early"') < page.index('id="late"')


def test_page_omits_empty_groups(b, template):
    page = b.page_html([{"repo": "demo-cli", "manifest": manifest()}], template)
    assert 'id="messages"' not in page


def test_page_nav_lists_used_groups(b, template):
    page = b.page_html([{"repo": "demo-cli", "manifest": manifest()}], template)
    assert '<nav><a href="#home">Home &amp; family</a><a href="privacy/">Privacy</a></nav>' in page


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q", "-p", "no:cacheprovider"]))
