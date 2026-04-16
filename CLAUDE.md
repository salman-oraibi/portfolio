# Portfolio Project

## Purpose

A pipeline for generating a personal portfolio website for job hunting.

The workflow extracts text and images from company branch PDF brochures, cross-references them
with a resume PDF, uses Claude to write story-style markdown posts, and renders everything into
a JS-driven single-page portfolio site.  
A built-in admin panel lets you write and publish new stories manually without re-running the pipeline.

---

## Folder Structure

```
portfolio-project/
├── data/                    # Drop PDF files here
│   ├── resume.pdf           # Your resume
│   ├── branch-a.pdf         # Company / branch brochure A
│   ├── branch-b.pdf         # Company / branch brochure B
│   ├── posts_config.json    # Per-post config (title, branch, pages, context_files, etc.)
│   └── context/             # Optional plain-text context files (briefs, reports, writeups)
│
├── scripts/                 # Python pipeline scripts
│   ├── extract_pdf.py       # Extracts text + images from a PDF → JSON
│   ├── generate_post.py     # Claude API: PDF pair → markdown post
│   ├── build_site.py        # Reads content/*.md → docs/posts.json + copies files
│   └── templates/           # (legacy Jinja template, unused)
│
├── content/                 # Generated markdown posts (one file per project)
│
├── docs/                    # Final static website (open index.html in a browser)
│   ├── index.html           # JS-driven portfolio page
│   ├── admin.html           # Admin panel — write & download new stories
│   ├── posts.json           # Manifest built by build_site.py
│   ├── content/             # Markdown files copied here by build_site.py
│   ├── images/              # Images extracted from PDFs (or uploaded via admin)
│   ├── css/
│   │   ├── style.css        # Main dark-theme stylesheet
│   │   └── admin.css        # Admin panel styles
│   └── js/
│       ├── app.js           # Fetches posts.json, renders cards + modal
│       └── admin.js         # Admin form logic (generate + download .md)
│
├── venv/                    # Python 3.12 virtual environment (not committed)
├── requirements.txt
├── CLAUDE.md                # This file
└── README.md
```

---

## Markdown Post Frontmatter

Every post in `content/` must have these frontmatter fields:

```yaml
---
title: "Post Title"
date: 2024-06-01
branch: "Company / Branch Name"   # used for the filter buttons
summary: "One or two sentence preview shown on the card."
tags:
  - React
  - Node.js
images:
  - screenshot.png              # filenames inside docs/images/
---
```

---

## Workflow

### A — AI-generated post from PDFs

#### 1. Add PDFs

Place files in `data/`:  
- `resume.pdf` — your resume  
- `branch-a.pdf`, `branch-b.pdf` — company brochures

#### 2. Install dependencies

```bash
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-...
```

#### 3. Generate a post

```bash
cd portfolio-project
python scripts/generate_post.py \
  --company data/branch-a.pdf \
  --resume  data/resume.pdf \
  --title   "Building a Real-Time Dashboard" \
  --branch  "Acme Corp"
```

Output: `content/building-a-real-time-dashboard.md`

#### 4. Build the manifest

```bash
python scripts/build_site.py
```

Copies `content/*.md` → `docs/content/` and writes `docs/posts.json`.

#### 5. Preview

```bash
python -m http.server 8080 --directory docs
# open http://localhost:8080
```

---

### B — Manual post via the admin panel

1. Serve the site: `python -m http.server 8080 --directory docs`
2. Open `http://localhost:8080/admin.html`
3. Fill in the form (title, summary, branch, tags, body in markdown, images)
4. Click **Download .md** → save the file to `content/`
5. Click **Download images** → save images to `docs/images/`
6. Run `python scripts/build_site.py`

---

## Scripts Reference

| Script | Purpose |
|---|---|
| `extract_pdf.py` | Standalone PDF extractor — prints JSON with pages + image paths |
| `generate_post.py` | Full AI pipeline: extract → call Claude → save markdown |
| `build_site.py` | Copies `content/*.md` to `docs/content/`, writes `docs/posts.json` |

---

## generate_post.py Features

### Extra context files (`--context-files`)

Pass one or more plain-text files to inject additional context into the prompt:

```bash
python scripts/generate_post.py \
  --company data/acme.pdf \
  --resume data/resume.pdf \
  --title "My Project" \
  --branch "Acme Corp" \
  --context-files data/context/acme_brief.txt data/context/project_notes.txt
```

- Each file is read and appended to the prompt under **ADDITIONAL CONTEXT / SUPPORTING DOCUMENTS**
- Content is truncated to 2000 chars per file to avoid bloating the prompt
- Store context files in `data/context/` (ignored by git except `.gitkeep`)
- The `context_files` array in `data/posts_config.json` records which files belong to each post

### Skills & Technologies section

Every generated post ends with a `## Skills & Technologies` section. Claude draws 6–10 skills from both the resume competencies and the project content, formatted as backtick-wrapped inline tags:

```
`Biomechanics` `Product Design` `Prototyping` `Digital Fabrication` `R&D Management`
```

### `data/posts_config.json`

Central config file listing all posts and their generation parameters:

```json
[
  {
    "title": "Post Title",
    "branch": "Company Name",
    "company": "data/brochure.pdf",
    "resume": "data/resume.pdf",
    "pages": "5-6",
    "context_files": ["data/context/brief.txt"]
  }
]
```

The `context_files` array is optional — omit it or leave it empty if no extra context is needed.

---

## Site Architecture

No backend, no database. Everything is flat files + browser JS.

- `docs/posts.json` — manifest of post metadata (title, summary, date, branch, tags, images)
- `docs/content/` — full markdown bodies, fetched on demand when a user opens a post
- `app.js` — fetches the manifest on load, renders filter buttons and card grid, opens posts in a modal
- `admin.js` — generates a valid markdown file with frontmatter for download; no server writes

---

## Current Status

**Phase 3 in progress — image filtering pipeline being refined**

### Completed

- Project scaffolded with all folders and files
- Python 3.12 venv set up with all dependencies including numpy
- PDF extraction working for both text and images
- `--skip-pages`, `--pages`, `--min-width`/`--min-height`, `--min-score`, `--jpeg-only` arguments added to `extract_pdf.py` and `generate_post.py`
- `generate_post.py` rewritten to save prompt to `content/prompt_draft.txt` instead of calling the API directly (using Claude Pro via Claude Code instead)
- Image scoring using Laplacian variance + color entropy implemented
- Scores confirmed: JPEGs score 2–12, decorative PNGs score ~0
- Default `--min-score` updated to 2.0, `--jpeg-only` flag added

## Pending UI Improvements

These are deferred until after all posts are generated and core functionality is complete.

1. **Post card image carousel** — hero image on each card should slowly cycle through the post's images automatically (crossfade transition, ~4 second interval)

2. **Post body image gallery** — images inside a post should render as a masonry or grid gallery instead of stacked one after another. Handle varying image sizes gracefully.

---

### Next Session — Pick Up Here

1. Test image filtering with: `--min-score 2.0 --jpeg-only`
2. Confirm image count is reasonable (target 5–15 per PDF)
3. Generate first portfolio post for Adidas Harden 7 project (pages 5–6)
4. Review and refine the generated markdown
5. Move to site rendering and admin panel
