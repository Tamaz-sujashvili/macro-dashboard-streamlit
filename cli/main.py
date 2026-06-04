#!/usr/bin/env python3
import json
import os
import subprocess
from pathlib import Path

import typer

app = typer.Typer(add_completion=False)

BASE_DIR = Path.home() / ".macro_dashboard"
POSTS_PATH = BASE_DIR / "x_intel_posts.json"
ANALYZED_PATH = BASE_DIR / "x_intel_analyzed.json"


def _load_count(path: Path) -> int:
    if not path.exists() or path.stat().st_size == 0:
        return 0
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle) or []
        return len(data)
    except Exception:
        return 0


@app.callback()
def app_callback() -> None:
    """X intelligence orchestrator."""


@app.command()
def run(
    max_images: int = typer.Option(30, help="Maximum number of images to analyze this run."),
    skip_scrape: bool = typer.Option(False, help="Reuse the cached scraped posts file."),
    accounts: str | None = typer.Option(None, help="Comma-separated override for TARGET_ACCOUNTS."),
    search_terms: str | None = typer.Option(None, help="Comma-separated X search terms override."),
) -> None:
    env = os.environ.copy()
    if accounts:
        env["X_TARGET_ACCOUNTS"] = accounts
    if search_terms:
        env["X_SEARCH_TERMS"] = search_terms
    env["MAX_IMAGES"] = str(max_images)

    root_dir = Path(__file__).resolve().parent.parent

    if not skip_scrape:
        subprocess.run(
            ["python3", "cli/x_scraper.py"],
            cwd=root_dir,
            env=env,
            check=True,
        )

    subprocess.run(
        ["bash", "cli/analyze_with_codex.sh"],
        cwd=root_dir,
        env=env,
        check=True,
    )

    posts_count = _load_count(POSTS_PATH)
    analyzed_count = _load_count(ANALYZED_PATH)

    print(f"Posts in cache: {posts_count}")
    print(f"Charts analyzed: {analyzed_count}")
    print(f"Output file: {ANALYZED_PATH}")


if __name__ == "__main__":
    app()
