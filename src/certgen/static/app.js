/**
 * Bulk Certificate Generator — Modern Reactive Client Application
 */

(function () {
  'use strict';

  // --- State ---
  let currentJobId = null;
  let pollingInterval = null;
  let currentCertificates = [];
  let activeFilter = 'all';
  let pollStartTime = null;

  // --- Presets Data ---
  const PRESETS = {
    valid: [
      { name: "Asha Patil", email: "asha@example.com", reference_id: "STU-001", achievement: "with Distinction" },
      { name: "Rohan Kulkarni", email: "rohan@example.com", reference_id: "STU-002", achievement: "First Class Honours" },
      { name: "Zoë Łukasz", email: "zoe@example.com", reference_id: "STU-003", achievement: "" }
    ],
    mixed: [
      { name: "Asha Patil", email: "asha@example.com", reference_id: "STU-001", achievement: "with Distinction" },
      { name: "Rohan Kulkarni", email: "rohan@example.com", reference_id: "STU-002", achievement: "" },
      { name: "Zoë Łukasz", email: "zoe@example.com", reference_id: "STU-003", achievement: "" },
      { name: "", email: "bad-email-format", reference_id: "ERR-001", achievement: "" },
      { name: "Asha Duplicate", email: "ASHA@example.com", reference_id: "ERR-002", achievement: "" }
    ],
    large: [
      { name: "Aarav Sharma", email: "aarav.sharma@example.com", reference_id: "STU-101", achievement: "Magna Cum Laude" },
      { name: "Aditi Rao", email: "aditi.rao@example.com", reference_id: "STU-102", achievement: "Honours" },
      { name: "Brian O'Connor", email: "brian.oc@example.com", reference_id: "STU-103", achievement: "" },
      { name: "Camila Rodriguez", email: "camila.r@example.com", reference_id: "STU-104", achievement: "High Distinction" },
      { name: "Dev Patel", email: "dev.patel@example.com", reference_id: "STU-105", achievement: "" },
      { name: "Elena Rostova", email: "elena.r@example.com", reference_id: "STU-106", achievement: "" },
      { name: "Farhan Akhtar", email: "farhan.a@example.com", reference_id: "STU-107", achievement: "Merit" },
      { name: "Grace Hopper", email: "grace.h@example.com", reference_id: "STU-108", achievement: "Outstanding Scholar" },
      { name: "Hassan Ali", email: "hassan.ali@example.com", reference_id: "STU-109", achievement: "" },
      { name: "Ishaan Verma", email: "ishaan.v@example.com", reference_id: "STU-110", achievement: "" },
      { name: "Jasmine Kaur", email: "jasmine.k@example.com", reference_id: "STU-111", achievement: "Honours" },
      { name: "Kenji Sato", email: "kenji.sato@example.com", reference_id: "STU-112", achievement: "" },
      { name: "Liam Smith", email: "liam.s@example.com", reference_id: "STU-113", achievement: "" },
      { name: "Meera Nair", email: "meera.nair@example.com", reference_id: "STU-114", achievement: "Distinction" },
      { name: "Noor Fatima", email: "noor.f@example.com", reference_id: "STU-115", achievement: "" }
    ]
  };

  // --- DOM Elements ---
  const healthPill = document.getElementById('health-status');
  const healthText = document.getElementById('health-text');

  const tplTitle = document.getElementById('tpl-title');
  const tplCourse = document.getElementById('tpl-course');
  const tplIssuer = document.getElementById('tpl-issuer');
  const tplDate = document.getElementById('tpl-date');
  const tplSignatory = document.getElementById('tpl-signatory');
  const tplSigTitle = document.getElementById('tpl-signatory-title');

  const previewTitle = document.getElementById('preview-title');
  const previewCourse = document.getElementById('preview-course');
  const previewIssuer = document.getElementById('preview-issuer');
  const previewDate = document.getElementById('preview-date');
  const previewName = document.getElementById('preview-name');
  const previewAchievement = document.getElementById('preview-achievement');
  const previewSignatory = document.getElementById('preview-signatory');
  const previewSigTitle = document.getElementById('preview-sig-title');

  const recipientsTbody = document.getElementById('recipients-tbody');
  const recipientCount = document.getElementById('recipient-count');
  const btnAddRow = document.getElementById('btn-add-row');

  const tabTable = document.getElementById('tab-table');
  const tabJson = document.getElementById('tab-json');
  const viewTable = document.getElementById('view-table');
  const viewJson = document.getElementById('view-json');
  const jsonRawInput = document.getElementById('json-raw-input');
  const btnSyncFromJson = document.getElementById('btn-sync-from-json');
  const jsonError = document.getElementById('json-error');

  const btnGenerate = document.getElementById('btn-generate');
  const chkIdempotent = document.getElementById('chk-idempotent');

  const sectionProgress = document.getElementById('section-progress');
  const jobMetaText = document.getElementById('job-meta-text');
  const jobStatusBadge = document.getElementById('job-status-badge');
  const progressBarFill = document.getElementById('progress-bar-fill');
  const progressPercent = document.getElementById('progress-percent');
  const progressTimer = document.getElementById('progress-timer');

  const metricTotal = document.getElementById('metric-total');
  const metricSucceeded = document.getElementById('metric-succeeded');
  const metricFailed = document.getElementById('metric-failed');
  const metricPending = document.getElementById('metric-pending');

  const sectionResults = document.getElementById('section-results');
  const btnDownloadZip = document.getElementById('btn-download-zip');
  const btnRetryFailed = document.getElementById('btn-retry-failed');
  const resultsTbody = document.getElementById('results-tbody');
  const filterSearch = document.getElementById('filter-search');

  const countAll = document.getElementById('count-all');
  const countSuccess = document.getElementById('count-success');
  const countFailed = document.getElementById('count-failed');

  const pdfModal = document.getElementById('pdf-modal');
  const pdfIframe = document.getElementById('pdf-iframe');
  const modalCertNum = document.getElementById('modal-cert-num');
  const modalDownloadLink = document.getElementById('modal-download-link');
  const modalClose = document.getElementById('modal-close');

  const jobsModal = document.getElementById('jobs-modal');
  const jobsModalTbody = document.getElementById('jobs-modal-tbody');
  const jobsModalClose = document.getElementById('jobs-modal-close');
  const btnViewRecentJobs = document.getElementById('btn-view-recent-jobs');

  const toastContainer = document.getElementById('toast-container');

  // --- Initialize App ---
  function init() {
    // Set default date to today
    const today = new Date().toISOString().split('T')[0];
    tplDate.value = today;

    // Check System Health
    checkHealth();

    // Load initial default preset (3 Valid)
    loadPreset('valid');

    // Attach Template Preview Listeners
    [tplTitle, tplCourse, tplIssuer, tplDate, tplSignatory, tplSigTitle].forEach(el => {
      el.addEventListener('input', updateCertificatePreview);
    });
    updateCertificatePreview();

    // Attach Preset Buttons
    document.getElementById('preset-valid').addEventListener('click', () => loadPreset('valid'));
    document.getElementById('preset-mixed').addEventListener('click', () => loadPreset('mixed'));
    document.getElementById('preset-large').addEventListener('click', () => loadPreset('large'));
    document.getElementById('preset-clear').addEventListener('click', clearRecipients);

    // Row Actions
    btnAddRow.addEventListener('click', () => addRecipientRow());
    recipientsTbody.addEventListener('input', onTableDataChange);

    // View Switching (Table vs JSON)
    tabTable.addEventListener('click', () => switchMode('table'));
    tabJson.addEventListener('click', () => switchMode('json'));
    btnSyncFromJson.addEventListener('click', syncJsonToTable);

    // Generation Trigger
    btnGenerate.addEventListener('click', submitJob);

    // Results Actions
    btnDownloadZip.addEventListener('click', downloadAllZip);
    btnRetryFailed.addEventListener('click', retryFailedItems);
    filterSearch.addEventListener('input', renderResultsTable);

    // Filter Tabs
    document.querySelectorAll('[data-filter]').forEach(tab => {
      tab.addEventListener('click', (e) => {
        document.querySelectorAll('[data-filter]').forEach(t => t.classList.remove('active'));
        e.currentTarget.classList.add('active');
        activeFilter = e.currentTarget.getAttribute('data-filter');
        renderResultsTable();
      });
    });

    // Modals
    modalClose.addEventListener('click', () => {
      pdfModal.style.display = 'none';
      pdfIframe.src = '';
    });
    pdfModal.addEventListener('click', (e) => {
      if (e.target === pdfModal) {
        pdfModal.style.display = 'none';
        pdfIframe.src = '';
      }
    });

    btnViewRecentJobs.addEventListener('click', openRecentJobsModal);
    jobsModalClose.addEventListener('click', () => { jobsModal.style.display = 'none'; });
    jobsModal.addEventListener('click', (e) => {
      if (e.target === jobsModal) jobsModal.style.display = 'none';
    });
  }

  // --- Health Check ---
  async function checkHealth() {
    try {
      const res = await fetch('/health');
      if (res.ok) {
        const data = await res.json();
        if (data.status === 'ok') {
          healthPill.className = 'health-pill health-online';
          healthText.textContent = 'System Online (DB Ready)';
          return;
        }
      }
      throw new Error('Health check returned non-ok');
    } catch {
      healthPill.className = 'health-pill health-offline';
      healthText.textContent = 'API Offline';
    }
  }

  // --- Toast Notifications ---
  function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast ${type === 'error' ? 'toast-error' : type === 'success' ? 'toast-success' : ''}`;
    toast.textContent = message;
    toastContainer.appendChild(toast);
    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transition = 'opacity 0.3s ease';
      setTimeout(() => toast.remove(), 300);
    }, 3500);
  }

  // --- Certificate Mockup Live Preview ---
  function updateCertificatePreview() {
    previewTitle.textContent = tplTitle.value || 'Certificate of Completion';
    previewCourse.textContent = tplCourse.value || 'Course Title';
    previewIssuer.textContent = tplIssuer.value || 'Issuing Organization';
    previewDate.textContent = `Issued: ${tplDate.value || 'YYYY-MM-DD'}`;
    previewSignatory.textContent = tplSignatory.value || 'Signatory Name';
    previewSigTitle.textContent = tplSigTitle.value || 'Signatory Title';

    // Sync first row recipient to preview
    const firstRow = recipientsTbody.querySelector('tr');
    if (firstRow) {
      const nameInput = firstRow.querySelector('.input-name');
      const achInput = firstRow.querySelector('.input-achievement');
      previewName.textContent = nameInput && nameInput.value.trim() ? nameInput.value.trim() : 'Recipient Name';
      previewAchievement.textContent = achInput && achInput.value.trim() ? achInput.value.trim() : '';
    } else {
      previewName.textContent = 'Recipient Name';
      previewAchievement.textContent = '';
    }
  }

  // --- Presets & Table Management ---
  function loadPreset(key) {
    const items = PRESETS[key] || [];
    recipientsTbody.innerHTML = '';
    items.forEach((item, idx) => addRecipientRow(item, idx + 1));
    updateRecipientCount();
    updateCertificatePreview();
    showToast(`Loaded ${items.length} recipients preset.`, 'info');
  }

  function clearRecipients() {
    recipientsTbody.innerHTML = '';
    addRecipientRow({ name: '', email: '', reference_id: '', achievement: '' }, 1);
    updateRecipientCount();
    updateCertificatePreview();
  }

  function addRecipientRow(data = {}, seq = null) {
    const tr = document.createElement('tr');
    const rowIdx = seq || (recipientsTbody.children.length + 1);

    tr.innerHTML = `
      <td class="text-muted text-center row-num">${rowIdx}</td>
      <td>
        <input type="text" class="table-input input-name" placeholder="Full Name" value="${escapeHtml(data.name || '')}" required>
      </td>
      <td>
        <input type="text" class="table-input input-email" placeholder="email@example.com" value="${escapeHtml(data.email || '')}" required>
      </td>
      <td>
        <input type="text" class="table-input input-ref" placeholder="ID or Ref" value="${escapeHtml(data.reference_id || '')}">
      </td>
      <td>
        <input type="text" class="table-input input-achievement" placeholder="Distinction / Grade" value="${escapeHtml(data.achievement || '')}">
      </td>
      <td style="text-align: center;">
        <button type="button" class="btn-icon-danger btn-remove-row" title="Remove row">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="3 6 5 6 21 6"></polyline>
            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
          </svg>
        </button>
      </td>
    `;

    tr.querySelector('.btn-remove-row').addEventListener('click', () => {
      if (recipientsTbody.children.length > 1) {
        tr.remove();
        renumberRows();
        updateRecipientCount();
        updateCertificatePreview();
      } else {
        showToast('At least one recipient row is required.', 'error');
      }
    });

    recipientsTbody.appendChild(tr);
    updateRecipientCount();
  }

  function renumberRows() {
    const rows = recipientsTbody.querySelectorAll('tr');
    rows.forEach((row, i) => {
      const numCell = row.querySelector('.row-num');
      if (numCell) numCell.textContent = i + 1;
    });
  }

  function updateRecipientCount() {
    recipientCount.textContent = recipientsTbody.children.length;
  }

  function onTableDataChange() {
    updateCertificatePreview();
  }

  // --- Switch Mode (Table vs Raw JSON) ---
  function switchMode(mode) {
    if (mode === 'json') {
      const currentList = getRecipientsFromTable();
      jsonRawInput.value = JSON.stringify(currentList, null, 2);
      viewTable.style.display = 'none';
      viewJson.style.display = 'block';
      tabTable.classList.remove('active');
      tabJson.classList.add('active');
      jsonError.textContent = '';
    } else {
      viewTable.style.display = 'block';
      viewJson.style.display = 'none';
      tabJson.classList.remove('active');
      tabTable.classList.add('active');
    }
  }

  function syncJsonToTable() {
    try {
      const parsed = JSON.parse(jsonRawInput.value);
      if (!Array.isArray(parsed)) throw new Error('Root JSON must be an array of recipient objects.');
      if (parsed.length === 0) throw new Error('Recipient array cannot be empty.');

      recipientsTbody.innerHTML = '';
      parsed.forEach((item, idx) => {
        addRecipientRow(item, idx + 1);
      });
      updateRecipientCount();
      updateCertificatePreview();
      switchMode('table');
      showToast(`Synced ${parsed.length} recipients to table.`, 'success');
    } catch (err) {
      jsonError.textContent = `JSON Error: ${err.message}`;
    }
  }

  function getRecipientsFromTable() {
    const rows = recipientsTbody.querySelectorAll('tr');
    const items = [];
    rows.forEach(r => {
      const name = r.querySelector('.input-name')?.value.trim() || '';
      const email = r.querySelector('.input-email')?.value.trim() || '';
      const ref = r.querySelector('.input-ref')?.value.trim() || '';
      const ach = r.querySelector('.input-achievement')?.value.trim() || '';
      const item = { name, email };
      if (ref) item.reference_id = ref;
      if (ach) item.achievement = ach;
      items.push(item);
    });
    return items;
  }

  // --- Submit Generation Job ---
  async function submitJob() {
    const recipients = getRecipientsFromTable();
    if (!recipients.length) {
      showToast('Please add at least 1 recipient.', 'error');
      return;
    }

    if (!tplCourse.value.trim() || !tplIssuer.value.trim() || !tplDate.value) {
      showToast('Please fill out all required template fields (Course, Issuer, Date).', 'error');
      return;
    }

    const payload = {
      certificate: {
        title: tplTitle.value.trim() || "Certificate of Completion",
        course_name: tplCourse.value.trim(),
        issuer_name: tplIssuer.value.trim(),
        issue_date: tplDate.value,
        signatory_name: tplSignatory.value.trim() || null,
        signatory_title: tplSigTitle.value.trim() || null
      },
      recipients: recipients
    };

    const headers = { 'Content-Type': 'application/json' };
    if (chkIdempotent.checked) {
      headers['Idempotency-Key'] = 'key_' + Date.now();
    }

    btnGenerate.disabled = true;
    btnGenerate.innerHTML = `<span class="spinner"></span> Dispatching Job...`;

    try {
      const res = await fetch('/api/v1/jobs', {
        method: 'POST',
        headers: headers,
        body: JSON.stringify(payload)
      });

      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        const msg = errorData.error?.message || 'Failed to submit certificate generation job.';
        throw new Error(msg);
      }

      const accepted = await res.json();
      currentJobId = accepted.id;

      // Reveal Progress Console & Scroll
      sectionProgress.style.display = 'block';
      sectionResults.style.display = 'none';
      sectionProgress.scrollIntoView({ behavior: 'smooth' });

      showToast(`Batch accepted (${accepted.id}). Generating...`, 'success');

      pollStartTime = Date.now();
      updateProgressUI(accepted.status, accepted.progress);
      startPolling(accepted.id);

    } catch (err) {
      showToast(err.message, 'error');
    } finally {
      btnGenerate.disabled = false;
      btnGenerate.innerHTML = `
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polygon points="5 3 19 12 5 21 5 3"></polygon>
        </svg>
        Generate Certificates
      `;
    }
  }

  // --- Polling Engine ---
  function startPolling(jobId) {
    if (pollingInterval) clearInterval(pollingInterval);

    pollingInterval = setInterval(async () => {
      try {
        const res = await fetch(`/api/v1/jobs/${jobId}`);
        if (!res.ok) throw new Error('Polling error');
        const job = await res.json();

        updateProgressUI(job.status, job.progress);

        const isTerminal = ['completed', 'completed_with_errors', 'failed'].includes(job.status);
        if (isTerminal) {
          clearInterval(pollingInterval);
          pollingInterval = null;
          onJobComplete(job);
        }
      } catch (err) {
        console.error('Polling failed:', err);
      }
    }, 800);
  }

  function updateProgressUI(status, progress) {
    jobMetaText.textContent = `Job ID: ${currentJobId} • Started ${new Date().toLocaleTimeString()}`;

    // Badge styling
    jobStatusBadge.className = `badge badge-${status}`;
    jobStatusBadge.textContent = status.replace(/_/g, ' ').toUpperCase();

    // Progress Bar
    const pct = Math.round(progress.percent_complete || 0);
    progressBarFill.style.width = `${pct}%`;
    progressPercent.textContent = `${pct}%`;

    const elapsed = ((Date.now() - pollStartTime) / 1000).toFixed(1);
    progressTimer.textContent = ['completed', 'completed_with_errors', 'failed'].includes(status)
      ? `Completed in ${elapsed}s`
      : `Processing... (${elapsed}s elapsed)`;

    // Metric Cards
    metricTotal.textContent = progress.total;
    metricSucceeded.textContent = progress.succeeded;
    metricFailed.textContent = progress.failed;
    metricPending.textContent = progress.pending;
  }

  async function onJobComplete(job) {
    showToast(`Job finished with status: ${job.status.replace(/_/g, ' ')}`, job.status === 'completed' ? 'success' : 'error');

    // Fetch full certificate results
    await fetchJobCertificates(job.id);

    // Show Results Section
    sectionResults.style.display = 'block';
    sectionResults.scrollIntoView({ behavior: 'smooth' });

    // Enable/Show Retry button if failed items exist
    if (job.progress.failed > 0 && job.status === 'completed_with_errors') {
      btnRetryFailed.style.display = 'inline-flex';
    } else {
      btnRetryFailed.style.display = 'none';
    }
  }

  // --- Fetch and Render Certificates ---
  async function fetchJobCertificates(jobId) {
    try {
      const res = await fetch(`/api/v1/jobs/${jobId}/certificates?limit=200`);
      if (!res.ok) throw new Error('Failed to load certificates list');
      const data = await res.json();
      currentCertificates = data.items || [];
      renderResultsTable();
    } catch (err) {
      showToast(err.message, 'error');
    }
  }

  function renderResultsTable() {
    const q = filterSearch.value.toLowerCase().trim();
    const filtered = currentCertificates.filter(item => {
      // Status filter tab
      if (activeFilter === 'success' && item.status !== 'success') return false;
      if (activeFilter === 'failed' && item.status !== 'failed') return false;

      // Text query
      if (q) {
        const nameMatch = (item.recipient_name || '').toLowerCase().includes(q);
        const emailMatch = (item.recipient_email || '').toLowerCase().includes(q);
        const certMatch = (item.certificate_number || '').toLowerCase().includes(q);
        return nameMatch || emailMatch || certMatch;
      }
      return true;
    });

    // Update Counter Badges
    countAll.textContent = currentCertificates.length;
    countSuccess.textContent = currentCertificates.filter(c => c.status === 'success').length;
    countFailed.textContent = currentCertificates.filter(c => c.status === 'failed').length;

    resultsTbody.innerHTML = '';
    if (filtered.length === 0) {
      resultsTbody.innerHTML = `<tr><td colspan="7" style="text-align:center; padding: 24px; color: var(--text-muted);">No certificates match current filter.</td></tr>`;
      return;
    }

    filtered.forEach(cert => {
      const tr = document.createElement('tr');
      const isSuccess = cert.status === 'success';
      const isFailed = cert.status === 'failed';

      const statusBadge = isSuccess
        ? `<span class="status-pill status-pill-success">● Success</span>`
        : isFailed
        ? `<span class="status-pill status-pill-failed">✕ Failed</span>`
        : `<span class="status-pill status-pill-pending">⏳ Pending</span>`;

      const errorText = isFailed && cert.error
        ? `<span class="error-text" title="${escapeHtml(cert.error.message)}"><strong>[${escapeHtml(cert.error.code)}]</strong> ${escapeHtml(cert.error.message)}</span>`
        : `<span class="text-muted">—</span>`;

      const actions = isSuccess
        ? `
          <button type="button" class="btn btn-secondary btn-sm btn-preview-pdf" data-id="${cert.id}" data-num="${cert.certificate_number}">
            Preview
          </button>
          <a href="/api/v1/certificates/${cert.id}/download" download class="btn btn-primary btn-sm">
            PDF
          </a>
        `
        : `
          <span class="text-muted" style="font-size: 0.8rem;">No file</span>
        `;

      tr.innerHTML = `
        <td class="text-muted" style="font-weight: 600;">#${cert.sequence}</td>
        <td><strong>${escapeHtml(cert.recipient_name || '—')}</strong></td>
        <td>${escapeHtml(cert.recipient_email || '—')}</td>
        <td><code class="text-muted">${escapeHtml(cert.certificate_number || '—')}</code></td>
        <td>${statusBadge}</td>
        <td style="max-width: 280px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${errorText}</td>
        <td style="text-align: right; white-space: nowrap;">${actions}</td>
      `;

      const previewBtn = tr.querySelector('.btn-preview-pdf');
      if (previewBtn) {
        previewBtn.addEventListener('click', () => openPdfModal(cert.id, cert.certificate_number));
      }

      resultsTbody.appendChild(tr);
    });
  }

  // --- Modal PDF Preview ---
  function openPdfModal(certId, certNum) {
    const downloadUrl = `/api/v1/certificates/${certId}/download`;
    modalCertNum.textContent = certNum || certId;
    modalDownloadLink.href = downloadUrl;
    pdfIframe.src = downloadUrl;
    pdfModal.style.display = 'flex';
  }

  // --- Bulk ZIP Download ---
  function downloadAllZip() {
    if (!currentJobId) return;
    const zipUrl = `/api/v1/jobs/${currentJobId}/download`;
    window.location.href = zipUrl;
    showToast('Starting bulk ZIP archive download...', 'success');
  }

  // --- Retry Failed Items ---
  async function retryFailedItems() {
    if (!currentJobId) return;
    btnRetryFailed.disabled = true;
    try {
      const res = await fetch(`/api/v1/jobs/${currentJobId}/retry`, { method: 'POST' });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.error?.message || 'Failed to retry job.');
      }
      const job = await res.json();
      showToast('Retry dispatched! Re-evaluating items...', 'info');

      pollStartTime = Date.now();
      updateProgressUI(job.status, job.progress);
      startPolling(job.id);
    } catch (err) {
      showToast(err.message, 'error');
    } finally {
      btnRetryFailed.disabled = false;
    }
  }

  // --- Recent Jobs Drawer ---
  async function openRecentJobsModal() {
    jobsModal.style.display = 'flex';
    jobsModalTbody.innerHTML = `<tr><td colspan="5" style="text-align:center; padding: 24px;">Loading recent jobs...</td></tr>`;

    try {
      const res = await fetch('/api/v1/jobs?page=1&page_size=10');
      if (!res.ok) throw new Error('Failed to load jobs');
      const data = await res.json();
      const jobs = data.items || [];

      if (jobs.length === 0) {
        jobsModalTbody.innerHTML = `<tr><td colspan="5" style="text-align:center; padding: 24px;">No past jobs found in database.</td></tr>`;
        return;
      }

      jobsModalTbody.innerHTML = '';
      jobs.forEach(j => {
        const tr = document.createElement('tr');
        const dt = new Date(j.created_at).toLocaleString();
        tr.innerHTML = `
          <td><code>${j.id}</code></td>
          <td>${dt}</td>
          <td><span class="badge badge-${j.status}">${j.status}</span></td>
          <td>${j.progress.succeeded}/${j.progress.total} (${Math.round(j.progress.percent_complete)}%)</td>
          <td>
            <button type="button" class="btn btn-secondary btn-sm btn-load-past-job" data-id="${j.id}">
              Inspect
            </button>
          </td>
        `;
        tr.querySelector('.btn-load-past-job').addEventListener('click', () => {
          jobsModal.style.display = 'none';
          currentJobId = j.id;
          sectionProgress.style.display = 'block';
          updateProgressUI(j.status, j.progress);
          onJobComplete(j);
        });
        jobsModalTbody.appendChild(tr);
      });
    } catch (err) {
      jobsModalTbody.innerHTML = `<tr><td colspan="5" style="text-align:center; color: var(--danger); padding: 24px;">${err.message}</td></tr>`;
    }
  }

  // --- Utility ---
  function escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  // Kickoff
  document.addEventListener('DOMContentLoaded', init);
})();
