"""
build_docs.py

Reads all markdown files in content/, parses their frontmatter, and writes
docs/posts.json (the manifest the JS app uses) and copies the .md files to
docs/content/ so they can be fetched by the browser.

Usage: python build_docs.py
"""

import json
import shutil
from pathlib import Path

import frontmatter


CONTENT_DIR = Path("content")
SITE_DIR = Path("docs")
SITE_CONTENT_DIR = SITE_DIR / "content"
IMAGES_SRC_DIR = Path("content/images")
IMAGES_DEST_DIR = SITE_DIR / "images"


def load_posts() -> list[dict]:
    posts = []
    for md_file in sorted(CONTENT_DIR.glob("*.md")):
        post = frontmatter.load(str(md_file))
        meta = dict(post.metadata)
        posts.append({
            "slug":    md_file.stem,
            "file":    f"content/{md_file.name}",
            "title":   meta.get("title", md_file.stem.replace("-", " ").title()),
            "summary": meta.get("summary", ""),
            "date":    str(meta.get("date", "")),
            "branch":  meta.get("branch", ""),
            "tags":    meta.get("tags") or [],
            "images":  meta.get("images") or [],
        })
    posts.sort(key=lambda p: p["date"], reverse=True)
    return posts


def build():
    SITE_DIR.mkdir(exist_ok=True)
    SITE_CONTENT_DIR.mkdir(exist_ok=True)
    IMAGES_DEST_DIR.mkdir(exist_ok=True)

    # Copy markdown files so the browser can fetch them
    md_copied = 0
    for md_file in CONTENT_DIR.glob("*.md"):
        shutil.copy2(md_file, SITE_CONTENT_DIR / md_file.name)
        md_copied += 1

    # Write manifest
    posts = load_posts()
    manifest_path = SITE_DIR / "posts.json"
    manifest_path.write_text(json.dumps(posts, indent=2, ensure_ascii=False), encoding="utf-8")

    # Copy only images referenced in post frontmatter
    referenced = {img for post in posts for img in post["images"]}
    img_copied = 0
    img_missing = []
    for filename in referenced:
        src = IMAGES_SRC_DIR / filename
        if src.exists():
            shutil.copy2(src, IMAGES_DEST_DIR / filename)
            img_copied += 1
        else:
            img_missing.append(filename)

    print(f"Copied {md_copied} markdown file(s) to docs/content/")
    print(f"Written docs/posts.json with {len(posts)} post(s)")
    print(f"Copied {img_copied} images for {len(posts)} posts")
    if img_missing:
        print(f"WARNING: {len(img_missing)} referenced image(s) not found in docs/images/:")
        for name in sorted(img_missing):
            print(f"  {name}")


if __name__ == "__main__":
    build()
