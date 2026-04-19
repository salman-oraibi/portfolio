"""
server.py

Flask local admin server for the portfolio project.

Usage:
    cd portfolio-project
    python scripts/server.py

Runs on http://127.0.0.1:5000
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import frontmatter
from flask import Flask, jsonify, request, send_file, send_from_directory
from flask_cors import CORS

# ---------------------------------------------------------------------------
# Paths — all relative to project root (one level up from scripts/)
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent
CONTENT_DIR = ROOT / "content"
BACKUPS_DIR = CONTENT_DIR / "backups"
DOCS_CONTENT_DIR = ROOT / "docs" / "content"
DOCS_IMAGES_DIR = ROOT / "docs" / "images"
CONTENT_IMAGES_DIR = ROOT / "content" / "images"
DATA_DIR = ROOT / "data"
CONTEXT_DIR = DATA_DIR / "context"

GENERATE_SCRIPT = ROOT / "scripts" / "generate_post.py"
BUILD_SCRIPT = ROOT / "scripts" / "build_site.py"

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = Flask(__name__)
CORS(app)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def slug_to_path(slug: str) -> Path:
    return CONTENT_DIR / f"{slug}.md"


def parse_post(md_path: Path) -> dict:
    post = frontmatter.load(str(md_path))
    meta = dict(post.metadata)
    return {
        "slug":    md_path.stem,
        "file":    f"content/{md_path.name}",
        "title":   meta.get("title", md_path.stem.replace("-", " ").title()),
        "summary": meta.get("summary", ""),
        "date":    str(meta.get("date", "")),
        "branch":  meta.get("branch", ""),
        "tags":    meta.get("tags") or [],
        "images":  meta.get("images") or [],
        "body":    post.content,
    }


def err(message: str, status: int = 400):
    return jsonify({"error": message}), status


# ---------------------------------------------------------------------------
# Routes — admin UI
# ---------------------------------------------------------------------------

@app.get("/")
def admin_ui():
    admin_html = ROOT / "docs" / "admin.html"
    if not admin_html.exists():
        return err("admin.html not found", 404)
    return send_file(admin_html)


@app.get("/images/<path:filename>")
def serve_image(filename: str):
    return send_from_directory(DOCS_IMAGES_DIR, filename)


@app.get("/content/<path:filename>")
def serve_content_file(filename: str):
    return send_from_directory(DOCS_CONTENT_DIR, filename)


# ---------------------------------------------------------------------------
# Routes — posts
# ---------------------------------------------------------------------------

@app.get("/api/posts")
def list_posts():
    posts = []
    for md_file in sorted(CONTENT_DIR.glob("*.md")):
        try:
            post = parse_post(md_file)
            post.pop("body", None)
            posts.append(post)
        except Exception as e:
            posts.append({"slug": md_file.stem, "error": str(e)})
    posts.sort(key=lambda p: p.get("date", ""), reverse=True)
    return jsonify(posts)


@app.get("/api/posts/<slug>")
def get_post(slug: str):
    path = slug_to_path(slug)
    if not path.exists():
        return err(f"Post '{slug}' not found", 404)
    try:
        return jsonify(parse_post(path))
    except Exception as e:
        return err(str(e), 500)


@app.post("/api/posts/<slug>")
def save_post(slug: str):
    data = request.get_json(silent=True)
    if not data or "content" not in data:
        return err("Request body must include 'content'")

    content = data["content"]
    path = slug_to_path(slug)

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
            (BACKUPS_DIR / f"{slug}.md.bak").write_text(
                path.read_text(encoding="utf-8"), encoding="utf-8"
            )
        path.write_text(content, encoding="utf-8")

        # Mirror to docs/content/
        DOCS_CONTENT_DIR.mkdir(parents=True, exist_ok=True)
        (DOCS_CONTENT_DIR / path.name).write_text(content, encoding="utf-8")
    except Exception as e:
        return err(str(e), 500)

    return jsonify({"ok": True, "slug": slug})


@app.get("/api/posts/<slug>/backup")
def get_backup(slug: str):
    bak = BACKUPS_DIR / f"{slug}.md.bak"
    if not bak.exists():
        return jsonify({"status": "none"})
    return jsonify({"status": "ready", "content": bak.read_text(encoding="utf-8")})


@app.delete("/api/posts/<slug>")
def delete_post(slug: str):
    path = slug_to_path(slug)
    if not path.exists():
        return err(f"Post '{slug}' not found", 404)

    deleted = []
    for target in [path, DOCS_CONTENT_DIR / path.name]:
        if target.exists():
            target.unlink()
            deleted.append(str(target.relative_to(ROOT)))

    return jsonify({"ok": True, "deleted": deleted})


# ---------------------------------------------------------------------------
# Routes — generation & publishing
# ---------------------------------------------------------------------------

@app.post("/api/generate")
def generate():
    data = request.get_json(silent=True) or {}

    title    = data.get("title", "").strip()
    branch   = data.get("branch", "").strip()
    company  = data.get("company", "").strip()
    company2 = data.get("company2", "").strip()

    if not title:
        return err("'title' is required")
    if not branch:
        return err("'branch' is required")
    if not company:
        return err("'company' is required")

    company_path = ROOT / company
    if not company_path.exists():
        return err(f"Company PDF not found: {company}")

    resume_path = DATA_DIR / "resume.pdf"
    if not resume_path.exists():
        return err("data/resume.pdf not found")

    cmd = [
        sys.executable, str(GENERATE_SCRIPT),
        "--resume",    str(resume_path),
        "--title",     title,
        "--branch",    branch,
        "--min-score", str(data.get("min_score", 2.0)),
    ]

    if company2:
        # Dual-source: use --company-files with optional per-file options
        company2_path = ROOT / company2
        if not company2_path.exists():
            return err(f"Secondary PDF not found: {company2}")

        def _spec(path: Path, pages: str, skip: int) -> str:
            s = str(path)
            if skip:
                s += f":skip={skip}"
            if pages:
                s += f":pages={pages}"
            return s

        spec1 = _spec(company_path,  str(data.get("pages", "")),  int(data.get("skip_pages", 0) or 0))
        spec2 = _spec(company2_path, str(data.get("pages2", "")), int(data.get("skip_pages2", 0) or 0))
        cmd += ["--company-files", spec1, spec2]
    else:
        cmd += ["--company", str(company_path)]
        if data.get("pages"):
            cmd += ["--pages", str(data["pages"])]
        if data.get("skip_pages"):
            cmd += ["--skip-pages", str(data["skip_pages"])]

    global_context = ROOT / "data" / "context" / "career_positioning.txt"
    cmd += ["--global-context", str(global_context)]

    extra_context = data.get("context", "").strip()
    if extra_context:
        CONTEXT_DIR.mkdir(parents=True, exist_ok=True)
        tmp_ctx = CONTEXT_DIR / "_inline_context.txt"
        tmp_ctx.write_text(extra_context, encoding="utf-8")
        cmd += ["--context-files", str(tmp_ctx)]

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, cwd=str(ROOT), timeout=120
        )
    except subprocess.TimeoutExpired:
        return err("generate_post.py timed out after 120s", 504)
    except Exception as e:
        return err(str(e), 500)

    draft_path = ROOT / "content" / "prompt_draft.txt"
    prompt_content = draft_path.read_text(encoding="utf-8") if draft_path.exists() else ""

    if result.returncode != 0:
        return err(result.stderr.strip() or "generate_post.py failed", 500)

    return jsonify({"ok": True, "prompt": prompt_content})


ENHANCE_INPUT  = CONTENT_DIR / "enhance_input.txt"
ENHANCE_OUTPUT = CONTENT_DIR / "enhance_output.txt"


@app.post("/api/enhance")
def enhance():
    data = request.get_json(silent=True) or {}
    text = data.get("text", "").strip()
    if not text:
        return err("'text' is required")

    context = data.get("context", "").strip()

    parts = []
    if context:
        parts.append(f"=== CONTEXT ===\n{context}\n")
    parts.append(f"=== POST BODY TO ENHANCE ===\n{text}\n")
    parts.append(
        "=== INSTRUCTIONS ===\n"
        "Rewrite the post body above with these goals:\n"
        "- Reframe any solo-developer language to reflect team leadership\n"
        "- This person is an R&D Leader and Innovation Strategist who leads\n"
        "  multi-disciplinary teams of designers, engineers and developers\n"
        "- Use language like \"I led\", \"I directed\", \"I coordinated\",\n"
        "  \"I oversaw\" rather than \"I built\" or \"I coded\"\n"
        "- Maintain the same structure and sections\n"
        "- Keep the Skills & Technologies section unchanged\n"
        "- Return only the improved markdown body, no preamble"
    )

    CONTENT_DIR.mkdir(parents=True, exist_ok=True)
    ENHANCE_INPUT.write_text("\n".join(parts), encoding="utf-8")
    ENHANCE_OUTPUT.write_text("", encoding="utf-8")

    return jsonify({
        "status": "ready",
        "input_file":  "content/enhance_input.txt",
        "output_file": "content/enhance_output.txt",
    })


@app.get("/api/enhance/result")
def enhance_result():
    if not ENHANCE_OUTPUT.exists():
        return jsonify({"status": "pending"})
    text = ENHANCE_OUTPUT.read_text(encoding="utf-8").strip()
    if not text:
        return jsonify({"status": "pending"})
    return jsonify({"status": "ready", "text": text})


@app.post("/api/publish")
def publish():
    try:
        result = subprocess.run(
            [sys.executable, str(BUILD_SCRIPT)],
            capture_output=True, text=True, cwd=str(ROOT), timeout=60
        )
    except subprocess.TimeoutExpired:
        return err("build_site.py timed out", 504)
    except Exception as e:
        return err(str(e), 500)

    if result.returncode != 0:
        return err(result.stderr.strip() or "build_site.py failed", 500)

    return jsonify({"ok": True, "output": result.stdout.strip()})


# ---------------------------------------------------------------------------
# Routes — uploads
# ---------------------------------------------------------------------------

@app.post("/api/upload/image")
def upload_image():
    if "file" not in request.files:
        return err("No file in request")

    f = request.files["file"]
    if not f.filename:
        return err("Empty filename")

    CONTENT_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    DOCS_IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    try:
        import re
        from PIL import Image

        img = Image.open(f.stream)

        # Flatten transparency → white background, normalise to RGB
        if img.mode in ("RGBA", "LA", "P"):
            bg = Image.new("RGB", img.size, (255, 255, 255))
            if img.mode == "P":
                img = img.convert("RGBA")
            if img.mode in ("RGBA", "LA"):
                bg.paste(img, mask=img.split()[-1])
            else:
                bg.paste(img)
            img = bg
        elif img.mode != "RGB":
            img = img.convert("RGB")

        # Resize so the longest side is at most 1200 px
        max_px = 1200
        w, h = img.size
        if max(w, h) > max_px:
            scale = max_px / max(w, h)
            img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

        # Build a safe output filename
        stem = re.sub(r"[^\w\-]", "_", Path(f.filename).stem)
        out_filename = f"{stem}.jpeg"

        dest_content = CONTENT_IMAGES_DIR / out_filename
        dest_docs    = DOCS_IMAGES_DIR / out_filename
        img.save(str(dest_content), "JPEG", quality=85, optimize=True)
        shutil.copy2(dest_content, dest_docs)
    except Exception as e:
        return err(str(e), 500)

    return jsonify({"ok": True, "filename": out_filename})


@app.post("/api/upload/context")
def upload_context():
    if "file" not in request.files:
        return err("No file in request")

    f = request.files["file"]
    if not f.filename:
        return err("Empty filename")

    filename = Path(f.filename).name
    suffix   = Path(filename).suffix.lower()

    if suffix not in {".txt", ".pdf"}:
        return err("Only .txt and .pdf files are accepted for context upload")

    CONTEXT_DIR.mkdir(parents=True, exist_ok=True)

    try:
        if suffix == ".pdf":
            import fitz  # PyMuPDF
            pdf_bytes = f.read()
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            text = "\n\n".join(page.get_text() for page in doc)
            doc.close()
            out_filename = Path(filename).stem + ".txt"
            (CONTEXT_DIR / out_filename).write_text(text, encoding="utf-8")
        else:
            out_filename = filename
            (CONTEXT_DIR / out_filename).write_bytes(f.read())
    except Exception as e:
        return err(str(e), 500)

    return jsonify({"ok": True, "filename": out_filename, "path": f"data/context/{out_filename}"})


# ---------------------------------------------------------------------------
# Routes — tags & branches
# ---------------------------------------------------------------------------

@app.get("/api/tags")
def list_tags():
    tags: set[str]     = set()
    branches: set[str] = set()
    for md_file in CONTENT_DIR.glob("*.md"):
        try:
            post = frontmatter.load(str(md_file))
            meta = dict(post.metadata)
            for t in (meta.get("tags") or []):
                if t:
                    tags.add(str(t))
            branch = meta.get("branch", "")
            if branch:
                # Branch can be "A & B" — store each component separately too
                for part in str(branch).split(" & "):
                    part = part.strip()
                    if part:
                        branches.add(part)
        except Exception:
            pass
    return jsonify({
        "tags":     sorted(tags, key=str.lower),
        "branches": sorted(branches, key=str.lower),
    })


# ---------------------------------------------------------------------------
# Routes — Job Application Tailoring (Phase 7)
# ---------------------------------------------------------------------------

OUTPUT_DIR     = CONTENT_DIR / "output"
TAILOR_INPUT   = CONTENT_DIR / "tailor_input.txt"


@app.get("/api/jobs/resumes")
def list_resumes():
    resumes = sorted(
        p.name for p in DATA_DIR.rglob("*.pdf")
        if "resume" in p.name.lower() or "cv" in p.name.lower()
    )
    return jsonify(resumes)


@app.post("/api/jobs/fetch-url")
def fetch_url():
    import re
    import requests as req

    data = request.get_json(silent=True) or {}
    url  = data.get("url", "").strip()
    if not url:
        return err("'url' is required")

    try:
        resp = req.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        html = resp.text
    except Exception as e:
        return err(f"Failed to fetch URL: {e}")

    # Strip tags, collapse whitespace
    text = re.sub(r"<style[^>]*>.*?</style>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<script[^>]*>.*?</script>", " ", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&[a-z]+;", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return jsonify({"text": text[:8000]})


@app.post("/api/jobs/tailor")
def tailor():
    import fitz

    data          = request.get_json(silent=True) or {}
    job_text      = data.get("job_text", "").strip()
    resume_file   = data.get("resume_file", "").strip()
    selected_posts = data.get("selected_posts", [])
    output_type   = data.get("output_type", "both")

    if not job_text:
        return err("'job_text' is required")
    if not resume_file:
        return err("'resume_file' is required")

    resume_path = DATA_DIR / resume_file
    if not resume_path.exists():
        return err(f"Resume not found: {resume_file}")

    # Extract resume text via PyMuPDF
    try:
        doc = fitz.open(str(resume_path))
        resume_text = "\n\n".join(page.get_text() for page in doc)
        doc.close()
    except Exception as e:
        return err(f"Failed to read resume PDF: {e}")

    # Load selected posts
    projects_parts = []
    for slug in selected_posts:
        md_path = CONTENT_DIR / f"{slug}.md"
        if not md_path.exists():
            continue
        try:
            post = frontmatter.load(str(md_path))
            title = post.metadata.get("title", slug)
            body  = post.content[:1500]
            projects_parts.append(f"### {title}\n{body}")
        except Exception:
            pass
    projects_section = "\n\n".join(projects_parts) if projects_parts else "(none selected)"

    include_resume      = output_type in ("resume", "both")
    include_coverletter = output_type in ("coverletter", "both")

    parts = [
        f"=== JOB POST ===\n{job_text}",
        f"=== CURRENT RESUME ===\n{resume_text}",
        f"=== RELEVANT PROJECTS ===\n{projects_section}",
    ]

    if include_resume:
        parts.append(
            "=== INSTRUCTIONS FOR RESUME ===\n"
            "Rewrite the resume to:\n"
            "- Match keywords from the job post for ATS optimization\n"
            "- Highlight most relevant experience and projects\n"
            "- Keep same sections but reorder/emphasize based on job requirements\n"
            "- Use action verbs and quantified achievements where possible\n"
            "- Output as structured JSON with sections:\n"
            "  {name, contact, summary, experience, education, skills, projects}"
        )

    if include_coverletter:
        parts.append(
            "=== INSTRUCTIONS FOR COVER LETTER ===\n"
            "Write a cover letter that:\n"
            "- Opens with a specific hook related to the role\n"
            "- References 2-3 specific projects from the portfolio\n"
            "- Connects experience to job requirements\n"
            "- Professional but personal tone\n"
            "- Max 400 words\n"
            "- Output as plain text with paragraph breaks"
        )

    CONTENT_DIR.mkdir(parents=True, exist_ok=True)
    TAILOR_INPUT.write_text("\n\n".join(parts), encoding="utf-8")

    return jsonify({"status": "ready", "input_file": "content/tailor_input.txt"})


TEMPLATES_DIR = ROOT / "scripts" / "templates"


@app.post("/api/jobs/generate-pdf")
def generate_pdf():
    from jinja2 import Environment, FileSystemLoader
    from weasyprint import HTML as WP_HTML

    data         = request.get_json(silent=True) or {}
    resume_json  = data.get("resume_json")
    cover_letter = data.get("cover_letter_text", "").strip()
    output_type  = data.get("output_type", "both")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    env    = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))
    result = {}

    if output_type in ("resume", "both") and resume_json:
        try:
            html = env.get_template("resume.html").render(resume=resume_json)
            WP_HTML(string=html).write_pdf(str(OUTPUT_DIR / "resume.pdf"))
            result["resume_url"] = "/output/resume.pdf"
        except Exception as e:
            return err(f"Resume PDF failed: {e}")

    if output_type in ("coverletter", "both") and cover_letter:
        try:
            from datetime import date as _date
            context = {
                "cover_letter": cover_letter,
                "name":    (resume_json or {}).get("name", ""),
                "contact": (resume_json or {}).get("contact", {}),
                "date":    _date.today().strftime("%-d %B %Y"),
            }
            html = env.get_template("coverletter.html").render(**context)
            WP_HTML(string=html).write_pdf(str(OUTPUT_DIR / "coverletter.pdf"))
            result["coverletter_url"] = "/output/coverletter.pdf"
        except Exception as e:
            return err(f"Cover letter PDF failed: {e}")

    return jsonify(result)


@app.get("/output/<path:filename>")
def serve_output(filename: str):
    return send_from_directory(OUTPUT_DIR, filename)


@app.get("/api/jobs/posts")
def list_posts_for_jobs():
    posts = []
    for md_file in sorted(CONTENT_DIR.glob("*.md")):
        try:
            post = frontmatter.load(str(md_file))
            posts.append({
                "slug":  md_file.stem,
                "title": post.metadata.get("title", md_file.stem.replace("-", " ").title()),
            })
        except Exception:
            pass
    posts.sort(key=lambda p: p["title"].lower())
    return jsonify(posts)


TAILOR_OUTPUT = CONTENT_DIR / "tailor_output.txt"


@app.get("/api/jobs/check-output")
def check_tailor_output():
    ready = TAILOR_OUTPUT.exists() and bool(TAILOR_OUTPUT.read_text(encoding="utf-8").strip())
    return jsonify({"ready": ready})


@app.get("/api/jobs/tailor-output")
def get_tailor_output():
    if not TAILOR_OUTPUT.exists():
        return err("tailor_output.txt not found — run the Claude Code command first", 404)
    return jsonify({"content": TAILOR_OUTPUT.read_text(encoding="utf-8")})


# ---------------------------------------------------------------------------
# Routes — PDFs
# ---------------------------------------------------------------------------

@app.get("/api/pdfs")
def list_pdfs():
    pdfs = sorted(
        str(p.relative_to(ROOT))
        for p in DATA_DIR.rglob("*.pdf")
    )
    return jsonify(pdfs)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    for d in [CONTENT_DIR, DOCS_CONTENT_DIR, DOCS_IMAGES_DIR,
              CONTENT_IMAGES_DIR, CONTEXT_DIR]:
        d.mkdir(parents=True, exist_ok=True)

    print("Portfolio admin server")
    print(f"  Root:    {ROOT}")
    print(f"  URL:     http://127.0.0.1:5000")

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("  WARNING: ANTHROPIC_API_KEY not set — /api/enhance will be unavailable")

    app.run(host="127.0.0.1", port=5000, debug=False)
