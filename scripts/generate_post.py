"""
generate_post.py

Extracts text from a company PDF and a resume PDF, builds a prompt for Claude,
saves it to content/prompt_draft.txt, and prints instructions for the next step.

Usage (single source PDF):
    python generate_post.py \
        --company data/acme.pdf \
        --resume data/resume.pdf \
        --title "My Project Title" \
        --branch "Acme Corp" \
        [--skip-pages N] \
        [--pages 5-6 | --pages 5,6,7] \
        [--min-score N]

Usage (multiple source PDFs):
    python generate_post.py \
        --company-files data/a.pdf:skip=4:pages=10 data/b.pdf:skip=8:pages=11 \
        --resume data/resume.pdf \
        --title "My Project Title" \
        --branch "Acme & Partner"
"""

import argparse
import sys
from datetime import date
from pathlib import Path

from extract_pdf import extract_pdf


def parse_pages(pages_arg: str) -> set[int]:
    """
    Parse a --pages argument into a set of page numbers.

    Accepts:
        "5-6"     → {5, 6}
        "5,6,7"   → {5, 6, 7}
        "5"       → {5}
    """
    pages = set()
    for part in pages_arg.split(","):
        part = part.strip()
        if "-" in part:
            start, _, end = part.partition("-")
            pages.update(range(int(start), int(end) + 1))
        else:
            pages.add(int(part))
    return pages


def parse_company_file_spec(spec: str) -> dict:
    """
    Parse a company file spec string of the form:
        path/to/file.pdf:skip=N:pages=X-Y

    All options are optional. Returns a dict with keys:
        path, skip_pages, pages (set[int] or None)
    """
    parts = spec.split(":")
    result = {"path": parts[0], "skip_pages": 0, "pages": None}
    for opt in parts[1:]:
        key, _, val = opt.partition("=")
        if key == "skip":
            result["skip_pages"] = int(val)
        elif key == "pages":
            result["pages"] = parse_pages(val)
    return result


def load_text(pdf_path: str, skip_pages: int = 0, pages: set[int] | None = None, min_score: float = 2.0, jpeg_only: bool = False) -> str:
    """
    Return text from a PDF as a single string.

    If pages is given, only include text from those page numbers.
    Otherwise include all pages (after skip_pages).
    """
    data = extract_pdf(pdf_path, skip_pages=skip_pages, min_score=min_score, jpeg_only=jpeg_only)
    return "\n\n".join(
        p["text"] for p in data["pages"]
        if pages is None or p["page"] in pages
    )


def get_extracted_images(
    pdf_path: str,
    skip_pages: int = 0,
    pages: set[int] | None = None,
    fallback_limit: int = 2,
    min_score: float = 2.0,
    jpeg_only: bool = False,
) -> list[str]:
    """
    Return basenames of images extracted from a PDF.

    If pages is given, only return images whose filename contains _p<N>_ for
    a page number in the set.

    If pages is not given, fall back to images from the first fallback_limit
    pages of content (i.e. pages skip_pages+1 through skip_pages+fallback_limit).
    """
    data = extract_pdf(pdf_path, skip_pages=skip_pages, min_score=min_score, jpeg_only=jpeg_only)
    all_images = [Path(entry["path"]).name for entry in data.get("images", [])]

    if pages is not None:
        return [img for img in all_images if _image_page(img) in pages]

    # Fallback: first fallback_limit pages after skip
    fallback_pages = set(range(skip_pages + 1, skip_pages + 1 + fallback_limit))
    return [img for img in all_images if _image_page(img) in fallback_pages]


def _image_page(filename: str) -> int | None:
    """
    Extract the page number from an image filename like 'doc_p5_img0.png'.
    Returns None if the pattern is not found.
    """
    import re
    match = re.search(r"_p(\d+)_", filename)
    return int(match.group(1)) if match else None


def build_prompt(
    resume_pdf: str,
    title: str,
    branch: str,
    company_pdf: str | None = None,
    skip_pages: int = 0,
    pages: set[int] | None = None,
    company_files: list[dict] | None = None,
    min_score: float = 2.0,
    jpeg_only: bool = False,
    context_files: list[str] | None = None,
    global_context_file: str | None = None,
) -> str:
    """
    Extract text from PDFs and return the full prompt string.

    Supply either company_pdf (single source) or company_files (multiple sources).
    company_files entries are dicts with keys: path, skip_pages, pages.
    """
    resume_text = load_text(resume_pdf, min_score=min_score, jpeg_only=jpeg_only)

    if company_files:
        # Multi-source: label each PDF's text block and collect all images
        context_blocks = []
        all_images = []
        for source in company_files:
            src_path = source["path"]
            src_skip = source.get("skip_pages", 0)
            src_pages = source.get("pages")
            label = Path(src_path).stem
            text = load_text(src_path, skip_pages=src_skip, pages=src_pages,
                             min_score=min_score, jpeg_only=jpeg_only)
            context_blocks.append(f"[{label}]\n{text[:3000]}")
            all_images += get_extracted_images(src_path, skip_pages=src_skip,
                                               pages=src_pages, min_score=min_score,
                                               jpeg_only=jpeg_only)
        company_context = "\n\n".join(context_blocks)
    else:
        company_context = load_text(company_pdf, skip_pages=skip_pages, pages=pages,
                                    min_score=min_score, jpeg_only=jpeg_only)[:6000]
        all_images = get_extracted_images(company_pdf, skip_pages=skip_pages, pages=pages,
                                          min_score=min_score, jpeg_only=jpeg_only)

    images_yaml = (
        "\nimages:\n" + "\n".join(f"  - {img}" for img in all_images)
        if all_images else ""
    )

    global_context_section = ""
    global_context_instructions = ""
    if global_context_file and Path(global_context_file).exists():
        text = Path(global_context_file).read_text(encoding="utf-8")[:3000]
        global_context_section = f"\n---\nCAREER POSITIONING & ROLE CONTEXT:\n{text}"
        global_context_instructions = (
            "Use the CAREER POSITIONING & ROLE CONTEXT above to:\n"
            "- Frame the author as a leader and decision-maker, not a solo practitioner\n"
            "- Align the narrative with the target roles mentioned in that context\n"
            "- Highlight skills and achievements that match the suggested career paths\n"
            "- Use seniority-appropriate language (led, drove, owned, architected, directed) throughout\n"
            "---\n"
        )

    additional_context_section = ""
    if context_files:
        parts = []
        for path in context_files:
            text = Path(path).read_text(encoding="utf-8")[:2000]
            parts.append(f"[{Path(path).name}]\n{text}")
        additional_context_section = "\n---\nADDITIONAL CONTEXT / SUPPORTING DOCUMENTS:\n" + "\n\n".join(parts)

    return f"""You are a professional technical writer helping a software engineer craft compelling portfolio posts for job hunting. Write in first person, story-driven style. Be specific, concrete, and engaging. Focus on the engineer's contributions, challenges overcome, and measurable impact. Output valid markdown only — no preamble, no code fences around the whole document.

---

Write a portfolio post titled "{title}" for the company/branch "{branch}".

Use the company/project context below to describe the work, and cross-reference the resume
to highlight specific skills and achievements that are relevant.

---
COMPANY / PROJECT CONTEXT:
{company_context}

---
RESUME:
{resume_text[:3000]}
{global_context_section}
{additional_context_section}
---
{global_context_instructions}Output a complete markdown document. Use this exact frontmatter block at the top, filling in
the values based on the content:

---
title: "{title}"
date: {date.today().isoformat()}
branch: "{branch}"
summary: "<one or two sentence hook — used as the card preview>"
tags:
  - <tag1>
  - <tag2>
  - <tag3>{images_yaml}
---

After the frontmatter write the post body with these sections:
1. Opening hook (expand on the summary)
2. The problem or challenge
3. What I built / contributed (with technical detail)
4. The outcome or impact
5. ## Skills & Technologies
   List 6–10 specific skills used in this project. Draw from both the resume competencies
   and the project content. Format each skill as a backtick-wrapped inline code tag, all on
   one line, space-separated. Example:
   `Biomechanics` `Product Design` `Prototyping` `Digital Fabrication` `R&D Management`
"""


def main():
    parser = argparse.ArgumentParser(description="Build a Claude prompt from PDFs and save it for use in Claude Code.")
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument("--company", help="Path to a single company brochure PDF")
    source_group.add_argument("--company-files", nargs="+", metavar="FILE[:skip=N][:pages=X]",
        help="One or more PDFs with optional per-file skip/pages, e.g. data/a.pdf:skip=4:pages=10")
    parser.add_argument("--resume", required=True, help="Path to resume PDF")
    parser.add_argument("--title", required=True, help="Post title")
    parser.add_argument("--branch", required=True, help="Company or branch name (e.g. 'Acme Corp')")
    parser.add_argument("--skip-pages", type=int, default=0, metavar="N", help="Skip the first N pages of the company PDF (single-source only)")
    parser.add_argument("--pages", metavar="RANGE", help="Pages to use from the company PDF (single-source only), e.g. '5-6' or '5,6,7'")
    parser.add_argument("--min-score", type=float, default=2.0, metavar="N", help="Minimum visual-interest score for extracted images (default 2.0)")
    parser.add_argument("--jpeg-only", action="store_true", default=False, help="Skip PNG images with score below 1.0 (usually decorative overlays)")
    parser.add_argument("--context-files", nargs="*", default=[], metavar="FILE", help="Additional text files providing extra context (truncated to 2000 chars each)")
    parser.add_argument("--global-context", default="data/context/career_positioning.txt", metavar="FILE", help="Global career positioning context file injected into every prompt (default: data/context/career_positioning.txt)")
    parser.add_argument("--output", help="Output .md file path (default: content/<slug>.md)")
    args = parser.parse_args()

    slug = args.title.lower().replace(" ", "-").replace("/", "-")
    output_path = Path(args.output) if args.output else Path("content") / f"{slug}.md"

    pages = parse_pages(args.pages) if args.pages else None
    company_files = [parse_company_file_spec(s) for s in args.company_files] if args.company_files else None

    print("Extracting text from PDFs ...")
    try:
        prompt = build_prompt(
            resume_pdf=args.resume,
            title=args.title,
            branch=args.branch,
            company_pdf=args.company,
            skip_pages=args.skip_pages,
            pages=pages,
            company_files=company_files,
            min_score=args.min_score,
            jpeg_only=args.jpeg_only,
            context_files=args.context_files,
            global_context_file=args.global_context,
        )
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    draft_path = Path("content/prompt_draft.txt")
    draft_path.parent.mkdir(parents=True, exist_ok=True)
    draft_path.write_text(prompt, encoding="utf-8")

    separator = "─" * 60

    print(f"\n{separator}")
    print("PROMPT SAVED")
    print(separator)
    print(prompt)
    print(separator)
    print("\nNext steps:")
    print(f"  1. The prompt has been saved to: {draft_path}")
    print(f"  2. Open Claude Code and run:  /paste content/prompt_draft.txt")
    print(f"  3. Then tell Claude Code:")
    print(f'     "Write the portfolio post based on this prompt and save it to {output_path}"')
    print(f"{separator}\n")


if __name__ == "__main__":
    main()
