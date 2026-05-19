const $ = (id) => document.getElementById(id);
const pretty = (data) => JSON.stringify(data, null, 2);

async function refreshDocs() {
  const res = await fetch('/api/documents');
  const docs = await res.json();
  $('docs').innerHTML = docs.map(d => `
    <div class="doc-item">
      <strong>ID ${d.id}: ${d.filename}</strong><br>
      Status: ${d.status}<br>
      Created: ${d.created_at}
    </div>
  `).join('') || '<p class="muted">No documents yet.</p>';
}

$('uploadForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  const form = new FormData(e.target);
  $('uploadResult').textContent = 'Processing...';
  const res = await fetch('/api/upload', { method: 'POST', body: form });
  const data = await res.json();
  $('uploadResult').textContent = pretty(data);
  await refreshDocs();
});

$('refreshDocs').addEventListener('click', refreshDocs);

$('retrieveBtn').addEventListener('click', async () => {
  const id = $('docId').value.trim();
  const form = new FormData();
  form.append('query', $('query').value.trim());
  form.append('top_k', '5');
  const res = await fetch(`/api/documents/${id}/retrieve`, { method: 'POST', body: form });
  const data = await res.json();
$('retrievalResult').innerHTML = renderEvidenceCards(data);
});

$('draftBtn').addEventListener('click', async () => {
  const id = $('draftDocId').value.trim();
  $('draftOutput').value = 'Generating...';
  const res = await fetch(`/api/documents/${id}/generate-draft`, { method: 'POST' });
  const data = await res.json();
  $('draftOutput').value = data.draft || pretty(data);
  $('downloadDraft').href = `/api/documents/${id}/download-draft`;
});

$('learnBtn').addEventListener('click', async () => {
  const id = $('draftDocId').value.trim();
  const form = new FormData();
  form.append('edited_draft', $('draftOutput').value);
  const res = await fetch(`/api/documents/${id}/learn-from-edit`, { method: 'POST', body: form });
  $('learnResult').textContent = pretty(await res.json());
});

refreshDocs();

function renderEvidenceCards(items) {
  if (!Array.isArray(items) || items.length === 0) {
    return '<p class="muted">No evidence found. Try another query.</p>';
  }

  return items.map((item, index) => {
    const score = item.score ? (item.score * 100).toFixed(2) + '%' : 'N/A';

    return `
      <div class="evidence-card">
        <div class="evidence-head">
          <span>Evidence ${index + 1}</span>
          <small>Page ${item.page || 'N/A'} | ${item.chunk_id || 'No chunk ID'} | Relevance ${score}</small>
        </div>
        <p>${escapeHtml(item.text || 'No text available')}</p>
      </div>
    `;
  }).join('');
}

function escapeHtml(text) {
  return String(text)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}
