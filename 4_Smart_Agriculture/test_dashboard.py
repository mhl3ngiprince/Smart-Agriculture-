"""Verify the dashboard renders real HTML with SVG icons and NO emoji.

This is a real regression guard: the brief requires web-page dashboards without
emoji icons, so we assert it.
"""
import re

import pytest

import dashboard
import database as db

EMOJI = re.compile(
    r"[\U0001F300-\U0001FAFF\u2600-\u27BF\u2b00-\u2bff\u2190-\u21FF"
    r"\u2300-\u23FF]")


@pytest.fixture()
def conn():
    import tempfile
    return db.get_conn(tempfile.mktemp(suffix=".db"))


def test_dashboard_renders_html(conn):
    html = dashboard.render(conn)
    assert html.startswith("<!doctype html>")
    assert "</html>" in html


def test_dashboard_uses_svg_not_emoji(conn):
    html = dashboard.render(conn)
    assert "<svg" in html, "icons must be inline SVG"
    assert EMOJI.findall(html) == [], "no emoji/icons from unicode ranges"


def test_dashboard_shows_data_source(conn):
    html = dashboard.render(conn)
    assert "Source:" in html, "every metric must be labelled with its source"
