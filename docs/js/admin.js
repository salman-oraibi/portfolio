/* admin.js — handles the new-story form */

const bodyTA   = document.getElementById('body');
const preview  = document.getElementById('preview');
const slugEl   = document.getElementById('preview-slug');
const imageIn  = document.getElementById('images');

let uploadedFiles = [];

/* ── Live preview ── */

bodyTA.addEventListener('input', updatePreview);

function updatePreview() {
  const md = bodyTA.value.trim();
  preview.innerHTML = md
    ? marked.parse(md)
    : '<p class="empty">Start writing to see a preview…</p>';
}

/* ── Slug hint ── */

document.getElementById('title').addEventListener('input', e => {
  slugEl.textContent = slugify(e.target.value) + '.md';
});

/* ── Image uploads ── */

imageIn.addEventListener('change', () => {
  uploadedFiles = Array.from(imageIn.files);
  const container = document.getElementById('image-previews');
  container.innerHTML = '';

  uploadedFiles.forEach(file => {
    const img = document.createElement('img');
    img.src = URL.createObjectURL(file);
    img.className = 'img-thumb';
    img.title = file.name;
    container.appendChild(img);
  });

  const note = document.getElementById('image-note');
  if (uploadedFiles.length) {
    note.textContent = `Copy these to site/images/: ${uploadedFiles.map(f => f.name).join(', ')}`;
    note.style.display = 'block';
    document.getElementById('download-images-btn').style.display = 'inline-flex';
  }
});

/* ── Generate markdown ── */

function buildMarkdown() {
  const title   = document.getElementById('title').value.trim();
  const summary = document.getElementById('summary').value.trim();
  const branch  = document.getElementById('branch').value.trim();
  const date    = document.getElementById('date').value || today();
  const tagsRaw = document.getElementById('tags').value.trim();
  const tags    = tagsRaw ? tagsRaw.split(',').map(t => t.trim()).filter(Boolean) : [];
  const body    = bodyTA.value.trim();

  const tagsYaml = tags.length
    ? '\ntags:\n' + tags.map(t => `  - ${t}`).join('\n')
    : '';
  const imagesYaml = uploadedFiles.length
    ? '\nimages:\n' + uploadedFiles.map(f => `  - ${f.name}`).join('\n')
    : '';

  return `---
title: "${title}"
date: ${date}
branch: "${branch}"
summary: "${summary}"${tagsYaml}${imagesYaml}
---

${body}
`;
}

/* ── Download .md ── */

document.getElementById('download-btn').addEventListener('click', () => {
  const title = document.getElementById('title').value.trim() || 'untitled';
  if (!title || title === 'untitled') {
    alert('Please enter a title before downloading.');
    return;
  }

  download(`${slugify(title)}.md`, buildMarkdown(), 'text/markdown');
  document.getElementById('download-note').style.display = 'block';
});

/* ── Download images ── */

document.getElementById('download-images-btn').addEventListener('click', async () => {
  for (const file of uploadedFiles) {
    download(file.name, file, file.type);
    await pause(120);
  }
});

/* ── Helpers ── */

function download(filename, data, type) {
  const blob = data instanceof Blob ? data : new Blob([data], { type });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}

function slugify(str) {
  return str.toLowerCase()
    .replace(/[^a-z0-9\s-]/g, '')
    .replace(/\s+/g, '-')
    .replace(/-+/g, '-')
    .trim();
}

function today() {
  return new Date().toISOString().split('T')[0];
}

function pause(ms) {
  return new Promise(r => setTimeout(r, ms));
}

/* ── Init ── */

document.getElementById('date').value = today();
updatePreview();
