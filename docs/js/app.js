/* app.js — loads posts.json and renders the portfolio */

const POSTS_JSON = 'posts.json';

let allPosts = [];
let activeBranch = null;

async function init() {
  try {
    const res = await fetch(POSTS_JSON);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    allPosts = await res.json();
  } catch {
    document.getElementById('posts-grid').innerHTML =
      '<p class="empty">No posts found. Run <code>python scripts/build_site.py</code> to generate them.</p>';
    return;
  }
  renderFilters();
  renderPosts(allPosts);
}

/* ── Filters ── */

function uniqueBranches() {
  return [...new Set(allPosts.map(p => p.branch).filter(Boolean))];
}

function renderFilters() {
  const branches = uniqueBranches();
  const container = document.getElementById('filters');
  if (!branches.length) { container.style.display = 'none'; return; }

  container.appendChild(makeFilterBtn('All', null));
  branches.forEach(b => container.appendChild(makeFilterBtn(b, b)));
}

function makeFilterBtn(label, value) {
  const btn = document.createElement('button');
  btn.textContent = label;
  btn.className = 'filter-btn' + (value === activeBranch ? ' active' : '');
  btn.addEventListener('click', () => {
    activeBranch = value;
    document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    renderPosts(value ? allPosts.filter(p => p.branch === value) : allPosts);
  });
  return btn;
}

/* ── Post cards ── */

function renderPosts(posts) {
  const grid = document.getElementById('posts-grid');
  grid.innerHTML = '';
  if (!posts.length) {
    grid.innerHTML = '<p class="empty">No posts for this filter.</p>';
    return;
  }
  posts.forEach(post => grid.appendChild(makeCard(post)));
}

function makeCard(post) {
  const card = document.createElement('article');
  card.className = 'card';

  const thumb = post.images?.[0]
    ? `<div class="card-thumb"><img src="images/${post.images[0]}" alt="" loading="lazy"></div>`
    : '';

  const branch = post.branch
    ? `<span class="branch-label">${escHtml(post.branch)}</span>`
    : '';

  const tags = (post.tags || [])
    .map(t => `<span class="tag">${escHtml(t)}</span>`).join('');

  card.innerHTML = `
    ${thumb}
    <div class="card-body">
      <div class="card-meta">${branch}<time datetime="${post.date}">${fmtDate(post.date)}</time></div>
      <h2 class="card-title">${escHtml(post.title)}</h2>
      <p class="card-summary">${escHtml(post.summary || '')}</p>
      <div class="tags">${tags}</div>
      <button class="read-btn">Read story →</button>
    </div>`;

  card.querySelector('.read-btn').addEventListener('click', () => openPost(post));
  return card;
}

/* ── Modal ── */

async function openPost(post) {
  const modal   = document.getElementById('modal');
  const content = document.getElementById('modal-content');

  content.innerHTML = '<p class="loading">Loading…</p>';
  modal.classList.add('open');
  document.body.style.overflow = 'hidden';

  try {
    const res = await fetch(post.file);
    if (!res.ok) throw new Error();
    const raw  = await res.text();
    const body = stripFrontmatter(raw);

    const branch = post.branch
      ? `<span class="branch-label">${escHtml(post.branch)}</span>` : '';
    const tags = (post.tags || [])
      .map(t => `<span class="tag">${escHtml(t)}</span>`).join('');
    const images = (post.images || [])
      .map(img => `<img src="images/${escHtml(img)}" alt="" class="post-img" loading="lazy">`)
      .join('');

    content.innerHTML = `
      <div class="post-meta">${branch}<time datetime="${post.date}">${fmtDate(post.date)}</time></div>
      <h1 id="modal-title">${escHtml(post.title)}</h1>
      <div class="tags">${tags}</div>
      ${images ? `<div class="post-images">${images}</div>` : ''}
      <div class="post-body">${marked.parse(body)}</div>`;
  } catch {
    content.innerHTML = '<p class="empty">Failed to load this post.</p>';
  }
}

function closeModal() {
  document.getElementById('modal').classList.remove('open');
  document.body.style.overflow = '';
}

document.getElementById('modal-close').addEventListener('click', closeModal);
document.getElementById('modal').addEventListener('click', e => {
  if (e.target.closest('.modal-overlay')) closeModal();
});
document.addEventListener('keydown', e => { if (e.key === 'Escape') closeModal(); });

/* ── Helpers ── */

function stripFrontmatter(text) {
  if (!text.startsWith('---')) return text;
  const parts = text.split('---');
  return parts.length >= 3 ? parts.slice(2).join('---').trim() : text;
}

function fmtDate(str) {
  if (!str) return '';
  try {
    return new Date(str).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
  } catch { return str; }
}

function escHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

init();
