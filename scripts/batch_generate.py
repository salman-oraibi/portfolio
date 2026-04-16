"""
batch_generate.py

Reads data/posts_config.json and runs generate_post.py for every post entry,
saving each prompt draft to content/prompts/<slug>.txt.

Usage:
    python scripts/batch_generate.py [--only "Post Title"] [--dry-run]

Options:
    --only TITLE   Process only the post whose title matches (substring match)
    --dry-run      Print what would be run without executing anything
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path


CONFIG_PATH = Path("data/posts_config.json")


def slug(title: str) -> str:
    return title.lower().replace(" ", "-").replace("/", "-").replace("'", "")


def main():
    parser = argparse.ArgumentParser(description="Batch-generate prompt drafts for all posts in posts_config.json.")
    parser.add_argument("--only", metavar="TITLE", help="Process only posts whose title contains this substring")
    parser.add_argument("--dry-run", action="store_true", help="Print commands without running them")
    parser.add_argument("--global-context", default="data/context/career_positioning.txt", metavar="FILE", help="Global career positioning context file passed to every post (default: data/context/career_positioning.txt)")
    args = parser.parse_args()

    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    defaults = config.get("defaults", {})
    posts = config.get("posts", [])

    resume = defaults.get("resume", "data/resume.pdf")
    default_min_score = defaults.get("min_score", 2.0)
    default_jpeg_only = defaults.get("jpeg_only", False)
    default_skip_pages = defaults.get("skip_pages", 0)

    output_dir = Path("content/prompts")
    output_dir.mkdir(parents=True, exist_ok=True)

    selected = [
        p for p in posts
        if args.only is None or args.only.lower() in p["title"].lower()
    ]

    if not selected:
        print(f"No posts matched filter: {args.only!r}", file=sys.stderr)
        sys.exit(1)

    print(f"Processing {len(selected)} post(s)...\n")

    for post in selected:
        title = post["title"]
        post_slug = slug(title)
        prompt_output = output_dir / f"{post_slug}.txt"

        cmd = [
            sys.executable, "scripts/generate_post.py",
            "--resume", post.get("resume", resume),
            "--title", title,
            "--branch", post["branch"],
            "--min-score", str(post.get("min_score", default_min_score)),
            "--output", f"content/{post_slug}.md",
        ]

        # Source PDFs: company_files (multi) or company (single)
        if "company_files" in post:
            specs = []
            for src in post["company_files"]:
                spec = src["path"]
                if "skip_pages" in src:
                    spec += f":skip={src['skip_pages']}"
                if "pages" in src:
                    spec += f":pages={src['pages']}"
                specs.append(spec)
            cmd += ["--company-files"] + specs
        else:
            cmd += ["--company", post["company"]]
            cmd += ["--skip-pages", str(post.get("skip_pages", default_skip_pages))]
            if post.get("pages"):
                cmd += ["--pages", post["pages"]]

        if post.get("jpeg_only", default_jpeg_only):
            cmd.append("--jpeg-only")

        context_files = post.get("context_files", [])
        if context_files:
            cmd += ["--context-files"] + context_files

        cmd += ["--global-context", args.global_context]

        print(f"  [{post_slug}]")
        if args.dry_run:
            print("  DRY RUN:", " ".join(cmd), "\n")
            continue

        result = subprocess.run(cmd, capture_output=True, text=True)

        # generate_post.py writes to content/prompt_draft.txt; copy to per-post path
        draft = Path("content/prompt_draft.txt")
        if draft.exists():
            prompt_output.write_text(draft.read_text(encoding="utf-8"), encoding="utf-8")
            print(f"  Prompt saved → {prompt_output}")
        else:
            print(f"  WARNING: prompt_draft.txt not found for '{title}'")

        if result.returncode != 0:
            print(f"  ERROR: {result.stderr.strip()}", file=sys.stderr)
        else:
            print(f"  Done.\n")


if __name__ == "__main__":
    main()
