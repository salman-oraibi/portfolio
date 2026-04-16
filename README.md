# Portfolio Generator

A Python pipeline that turns company PDF brochures + a resume into a clean,
story-driven portfolio website — powered by Claude.  
Comes with a built-in admin panel for writing stories manually.

---

## Quick Start (AI pipeline)

```bash
# 1. Install Python dependencies
pip install -r requirements.txt

# 2. Set your Anthropic API key
export ANTHROPIC_API_KEY=sk-...

# 3. Drop PDFs into data/
#    data/resume.pdf
#    data/branch-a.pdf
#    data/branch-b.pdf

# 4. Generate a post for each company PDF
python scripts/generate_post.py \
  --company data/branch-a.pdf \
  --resume  data/resume.pdf \
  --title   "What I Built at Acme" \
  --branch  "Acme Corp"

# 5. Build the site manifest
python scripts/build_site.py

# 6. Preview
python -m http.server 8080 --directory site
# → open http://localhost:8080
```

---

## Quick Start (admin panel)

```bash
python -m http.server 8080 --directory site
# → open http://localhost:8080/admin.html
```

Fill in the form, click **Download .md**, move it to `content/`, then re-run
`python scripts/build_site.py`.

---

## How It Works

```
PDFs  ──extract_pdf.py──▶  text + images
                                │
                    generate_post.py (Claude API)
                                │
                         content/*.md
                                │
                         build_site.py
                                │
                  site/posts.json + site/content/
                                │
                      Browser (app.js) renders
                       cards, filters, modal
```

| Stage | Script | Output |
|---|---|---|
| Extract | `extract_pdf.py` | JSON (text + image paths) |
| Generate | `generate_post.py` | `content/<slug>.md` |
| Build | `build_site.py` | `site/posts.json`, `site/content/` |

---

## Post Frontmatter

```yaml
---
title: "Post Title"
date: 2024-06-01
branch: "Company Name"
summary: "Short card preview."
tags:
  - Python
  - React
images:
  - screenshot.png
---
```

---

## Project Structure

```
data/        ← PDFs (resume + company brochures)
scripts/     ← pipeline scripts
content/     ← generated / hand-written markdown posts
site/        ← static website
  index.html     portfolio page
  admin.html     write new stories
  posts.json     built manifest
  content/       markdown files (auto-copied)
  images/        extracted / uploaded images
  css/           style.css + admin.css
  js/            app.js + admin.js
```

---

## Requirements

- Python 3.10+
- An [Anthropic API key](https://console.anthropic.com/) (only needed for the AI pipeline)
