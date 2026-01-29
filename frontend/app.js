/**
 * Cold Outreach - Frontend Application
 */

const API_BASE = '/api';

// State
let leads = [];
let currentLead = null;
let pagination = {
    page: 1,
    pageSize: 100,
    total: 0,
    totalPages: 1
};

// DOM Elements
const uploadSection = document.getElementById('uploadSection');
const dashboardSection = document.getElementById('dashboardSection');
const uploadZone = document.getElementById('uploadZone');
const fileInput = document.getElementById('fileInput');
const leadsTableBody = document.getElementById('leadsTableBody');
const leadModal = document.getElementById('leadModal');

// Initialize
document.addEventListener('DOMContentLoaded', init);

async function init() {
    setupEventListeners();
    await checkStatus();
}

function setupEventListeners() {
    // Upload
    uploadZone.addEventListener('click', () => fileInput.click());
    uploadZone.addEventListener('dragover', handleDragOver);
    uploadZone.addEventListener('dragleave', handleDragLeave);
    uploadZone.addEventListener('drop', handleDrop);
    fileInput.addEventListener('change', handleFileSelect);

    // Toolbar buttons
    document.getElementById('btnVerifyAll').addEventListener('click', verifyAll);
    document.getElementById('btnScanAll').addEventListener('click', scanAll);
    document.getElementById('btnGenerateDrafts').addEventListener('click', generateDraftsAll);
    document.getElementById('btnUploadNew').addEventListener('click', showUploadSection);
    document.getElementById('btnDownload').addEventListener('click', downloadExcel);

    // Filters
    document.getElementById('filterVerified').addEventListener('change', applyFilters);
    document.getElementById('filterDraft').addEventListener('change', applyFilters);
    document.getElementById('filterSent').addEventListener('change', applyFilters);
    document.getElementById('pageSize').addEventListener('change', handlePageSizeChange);
    document.getElementById('searchInput').addEventListener('input', debounce(applyFilters, 300));

    // Pagination
    document.getElementById('btnPrevPage').addEventListener('click', () => goToPage(pagination.page - 1));
    document.getElementById('btnNextPage').addEventListener('click', () => goToPage(pagination.page + 1));

    // Modal
    document.getElementById('modalBackdrop').addEventListener('click', closeModal);
    document.getElementById('modalClose').addEventListener('click', closeModal);
    document.getElementById('btnScanOne').addEventListener('click', scanCurrentLead);
    document.getElementById('btnGenerateOne').addEventListener('click', generateDraftCurrent);
    document.getElementById('btnGenerateReply').addEventListener('click', generateReplyCurrent);
    document.getElementById('btnSave').addEventListener('click', saveCurrentLead);
    document.getElementById('btnSend').addEventListener('click', sendCurrentLead);
}

// API Functions
async function fetchAPI(endpoint, options = {}) {
    try {
        const response = await fetch(`${API_BASE}${endpoint}`, {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            ...options
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'API Error');
        }

        return await response.json();
    } catch (error) {
        showToast(error.message, 'error');
        throw error;
    }
}

async function checkStatus() {
    try {
        const status = await fetchAPI('/status');

        if (status.file_loaded) {
            showDashboard();
            updateHeaderStats(status);
            await loadLeads();
            await updateStats();
        }
    } catch (error) {
        // No file loaded yet, stay on upload
    }
}

async function loadLeads() {
    const filterVerified = document.getElementById('filterVerified').value;
    const filterDraft = document.getElementById('filterDraft').value;
    const filterSent = document.getElementById('filterSent').value;
    const search = document.getElementById('searchInput').value;
    const pageSize = document.getElementById('pageSize')?.value || pagination.pageSize;

    let params = new URLSearchParams();
    if (filterVerified) params.append('email_verified', filterVerified);
    if (filterDraft) params.append('has_draft', filterDraft);
    if (filterSent) params.append('sequence_step', filterSent);
    if (search) params.append('search', search);
    params.append('page', pagination.page);
    params.append('page_size', pageSize);

    try {
        const response = await fetchAPI(`/leads?${params.toString()}`);
        leads = response.leads;
        pagination = {
            page: response.pagination.page,
            pageSize: response.pagination.page_size,
            total: response.pagination.total,
            totalPages: response.pagination.total_pages,
            hasNext: response.pagination.has_next,
            hasPrev: response.pagination.has_prev
        };
        renderLeadsTable();
        updatePaginationControls();
    } catch (error) {
        leads = [];
        renderLeadsTable();
    }
}

async function updateStats() {
    try {
        const stats = await fetchAPI('/leads/stats/summary');

        document.getElementById('totalLeads').textContent = stats.total;
        document.getElementById('validCount').textContent = stats.verified.valid;
        document.getElementById('invalidCount').textContent = stats.verified.invalid;
        document.getElementById('scannedCount').textContent = stats.scanned.scanned;
        document.getElementById('sentCount').textContent = stats.sent.sent;
    } catch (error) {
        // Ignore
    }
}

// File Upload
function handleDragOver(e) {
    e.preventDefault();
    uploadZone.classList.add('dragover');
}

function handleDragLeave(e) {
    e.preventDefault();
    uploadZone.classList.remove('dragover');
}

function handleDrop(e) {
    e.preventDefault();
    uploadZone.classList.remove('dragover');

    const files = e.dataTransfer.files;
    if (files.length > 0) {
        uploadFile(files[0]);
    }
}

function handleFileSelect(e) {
    const files = e.target.files;
    if (files.length > 0) {
        uploadFile(files[0]);
    }
}

async function uploadFile(file) {
    if (!file.name.endsWith('.xlsx') && !file.name.endsWith('.xls')) {
        showToast('Please upload an Excel file (.xlsx)', 'error');
        return;
    }

    const formData = new FormData();
    formData.append('file', file);

    const uploadProgress = document.getElementById('uploadProgress');
    const progressFill = document.getElementById('progressFill');
    const uploadStatus = document.getElementById('uploadStatus');

    uploadProgress.style.display = 'block';
    progressFill.style.width = '30%';
    uploadStatus.textContent = 'Uploading...';

    try {
        const response = await fetch(`${API_BASE}/upload`, {
            method: 'POST',
            body: formData
        });

        progressFill.style.width = '70%';
        uploadStatus.textContent = 'Processing...';

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Upload failed');
        }

        const result = await response.json();

        progressFill.style.width = '100%';
        uploadStatus.textContent = 'Done!';

        showToast(`Loaded ${result.leads_count} leads`, 'success');

        setTimeout(() => {
            showDashboard();
            loadLeads();
            updateStats();
        }, 500);

    } catch (error) {
        showToast(error.message, 'error');
        uploadProgress.style.display = 'none';
    }
}

function showUploadSection() {
    uploadSection.style.display = 'flex';
    dashboardSection.style.display = 'none';
}

function showDashboard() {
    uploadSection.style.display = 'none';
    dashboardSection.style.display = 'flex';
}

// Table Rendering
function renderLeadsTable() {
    const tableEmpty = document.getElementById('tableEmpty');

    if (leads.length === 0) {
        leadsTableBody.innerHTML = '';
        tableEmpty.style.display = 'block';
        return;
    }

    tableEmpty.style.display = 'none';

    leadsTableBody.innerHTML = leads.map(lead => `
        <tr data-id="${lead.id}">
            <td class="lead-name">${escapeHtml(lead.name || '-')}</td>
            <td class="lead-email">${escapeHtml(lead.email || '-')}</td>
            <td>
                ${lead.website ? `<a href="${escapeHtml(lead.website)}" class="lead-website" target="_blank">${truncate(lead.website, 30)}</a>` : '-'}
            </td>
            <td><span class="badge badge-${lead.email_verified}">${lead.email_verified}</span></td>
            <td><span class="badge badge-${lead.website_scan_summary ? 'yes' : 'no'}">${lead.website_scan_summary ? 'Yes' : 'No'}</span></td>
            <td><span class="badge badge-${lead.email_draft ? 'yes' : 'no'}">${lead.email_draft ? 'Yes' : 'No'}</span></td>
            <td><span class="badge badge-${lead.sequence_step === 'not_sent' ? 'no' : 'yes'}">${formatStep(lead.sequence_step)}</span></td>
            <td>
                <button class="btn btn-sm btn-secondary" onclick="openLeadModal(${lead.id})">
                    View
                </button>
            </td>
        </tr>
    `).join('');
}

function formatStep(step) {
    const steps = {
        'not_sent': 'Not Sent',
        'initial_sent': 'Sent',
        'ghost_1_sent': 'Follow-up 1',
        'ghost_2_sent': 'Follow-up 2',
        'replied': 'Replied'
    };
    return steps[step] || step;
}

// Bulk Actions
async function verifyAll() {
    try {
        const result = await fetchAPI('/verify', {
            method: 'POST',
            body: JSON.stringify({})
        });

        showToast(result.message, 'info');
        startProgressPolling('verify', 'Verifying emails');
    } catch (error) {
        // Error shown by fetchAPI
    }
}

async function scanAll() {
    try {
        const result = await fetchAPI('/scan', {
            method: 'POST',
            body: JSON.stringify({})
        });

        showToast(result.message, 'info');
        startProgressPolling('scan', 'Scanning websites');
    } catch (error) {
        // Error shown by fetchAPI
    }
}

async function generateDraftsAll() {
    try {
        const result = await fetchAPI('/generate-drafts', {
            method: 'POST',
            body: JSON.stringify({})
        });

        showToast(result.message, 'info');
        startProgressPolling('draft', 'Generating drafts');
    } catch (error) {
        // Error shown by fetchAPI
    }
}

async function startProgressPolling(operation, label) {
    const progressDiv = document.getElementById('operationProgress');
    const operationName = document.getElementById('operationName');
    const operationCount = document.getElementById('operationCount');
    const operationFill = document.getElementById('operationFill');
    const operationCurrent = document.getElementById('operationCurrent');

    progressDiv.style.display = 'block';
    operationName.textContent = label + '...';

    const poll = async () => {
        try {
            const progress = await fetchAPI(`/progress/${operation}`);

            const percent = progress.total > 0 ? (progress.completed / progress.total) * 100 : 0;
            operationCount.textContent = `${progress.completed}/${progress.total}`;
            operationFill.style.width = `${percent}%`;
            operationCurrent.textContent = progress.current || '';

            if (progress.running) {
                setTimeout(poll, 1000);
            } else {
                progressDiv.style.display = 'none';
                showToast(`${label} complete!`, 'success');
                loadLeads();
                updateStats();
            }
        } catch (error) {
            progressDiv.style.display = 'none';
        }
    };

    poll();
}

async function downloadExcel() {
    try {
        const response = await fetch(`${API_BASE}/download`);

        if (!response.ok) {
            throw new Error('Download failed');
        }

        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `leads_export_${new Date().toISOString().slice(0, 10)}.xlsx`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        a.remove();

        showToast('Excel downloaded!', 'success');
    } catch (error) {
        showToast(error.message, 'error');
    }
}

// Modal Functions
async function openLeadModal(leadId) {
    try {
        currentLead = await fetchAPI(`/leads/${leadId}`);

        document.getElementById('modalLeadName').textContent = currentLead.name || 'Lead Details';
        document.getElementById('modalEmail').textContent = currentLead.email || '-';
        document.getElementById('modalVerified').textContent = currentLead.email_verified;
        document.getElementById('modalVerified').className = `badge badge-${currentLead.email_verified}`;

        const websiteEl = document.getElementById('modalWebsite');
        if (currentLead.website) {
            websiteEl.href = currentLead.website.startsWith('http') ? currentLead.website : `https://${currentLead.website}`;
            websiteEl.textContent = currentLead.website;
        } else {
            websiteEl.href = '#';
            websiteEl.textContent = '-';
        }

        document.getElementById('modalCategory').textContent = currentLead.category || '-';
        document.getElementById('modalCity').textContent = currentLead.city || '-';

        const scanSummary = document.getElementById('modalScanSummary');
        scanSummary.innerHTML = currentLead.website_scan_summary
            ? escapeHtml(currentLead.website_scan_summary)
            : '<span class="placeholder">Not scanned yet</span>';

        document.getElementById('modalNotes').value = currentLead.my_notes || '';
        document.getElementById('modalSubject').value = currentLead.email_subject || '';
        document.getElementById('modalBody').value = currentLead.email_draft || '';
        document.getElementById('modalTheirReply').value = currentLead.their_last_reply || '';
        document.getElementById('modalStatus').textContent = formatStep(currentLead.sequence_step);

        leadModal.style.display = 'flex';
    } catch (error) {
        // Error shown by fetchAPI
    }
}

function closeModal() {
    leadModal.style.display = 'none';
    currentLead = null;
}

async function scanCurrentLead() {
    if (!currentLead) return;

    try {
        const btn = document.getElementById('btnScanOne');
        btn.disabled = true;
        btn.innerHTML = '<span class="btn-icon">⏳</span> Scanning...';

        await fetchAPI('/scan', {
            method: 'POST',
            body: JSON.stringify({ lead_ids: [currentLead.id] })
        });

        // Wait a bit then refresh
        setTimeout(async () => {
            await openLeadModal(currentLead.id);
            btn.disabled = false;
            btn.innerHTML = '<span class="btn-icon">🔍</span> Scan Now';
            showToast('Website scanned!', 'success');
        }, 2000);

    } catch (error) {
        btn.disabled = false;
        btn.innerHTML = '<span class="btn-icon">🔍</span> Scan Now';
    }
}

async function generateDraftCurrent() {
    if (!currentLead) return;

    // Save notes first
    await saveCurrentLead(false);

    try {
        const btn = document.getElementById('btnGenerateOne');
        btn.disabled = true;
        btn.innerHTML = '<span class="btn-icon">⏳</span> Generating...';

        const result = await fetchAPI(`/leads/${currentLead.id}/generate-draft?draft_type=initial`, {
            method: 'POST'
        });

        document.getElementById('modalSubject').value = result.subject;
        document.getElementById('modalBody').value = result.body;

        btn.disabled = false;
        btn.innerHTML = '<span class="btn-icon">✍️</span> Generate Draft';
        showToast('Draft generated!', 'success');

    } catch (error) {
        btn.disabled = false;
        btn.innerHTML = '<span class="btn-icon">✍️</span> Generate Draft';
    }
}

async function generateReplyCurrent() {
    if (!currentLead) return;

    const theirReply = document.getElementById('modalTheirReply').value;
    if (!theirReply.trim()) {
        showToast('Paste their reply first', 'warning');
        return;
    }

    // Save their reply first
    await fetchAPI(`/leads/${currentLead.id}`, {
        method: 'PUT',
        body: JSON.stringify({ their_last_reply: theirReply })
    });

    try {
        const btn = document.getElementById('btnGenerateReply');
        btn.disabled = true;
        btn.innerHTML = '<span class="btn-icon">⏳</span> Generating...';

        const result = await fetchAPI(`/leads/${currentLead.id}/generate-draft?draft_type=reply`, {
            method: 'POST'
        });

        document.getElementById('modalSubject').value = result.subject;
        document.getElementById('modalBody').value = result.body;

        btn.disabled = false;
        btn.innerHTML = '<span class="btn-icon">💬</span> Generate Reply';
        showToast('Reply draft generated!', 'success');

    } catch (error) {
        btn.disabled = false;
        btn.innerHTML = '<span class="btn-icon">💬</span> Generate Reply';
    }
}

async function saveCurrentLead(showMessage = true) {
    if (!currentLead) return;

    try {
        const updates = {
            my_notes: document.getElementById('modalNotes').value,
            email_subject: document.getElementById('modalSubject').value,
            email_draft: document.getElementById('modalBody').value,
            their_last_reply: document.getElementById('modalTheirReply').value
        };

        await fetchAPI(`/leads/${currentLead.id}`, {
            method: 'PUT',
            body: JSON.stringify(updates)
        });

        if (showMessage) {
            showToast('Changes saved!', 'success');
        }

        loadLeads();

    } catch (error) {
        // Error shown by fetchAPI
    }
}

async function sendCurrentLead() {
    if (!currentLead) return;

    const subject = document.getElementById('modalSubject').value;
    const body = document.getElementById('modalBody').value;

    if (!subject.trim() || !body.trim()) {
        showToast('Subject and body are required', 'warning');
        return;
    }

    // Save first
    await saveCurrentLead(false);

    try {
        const btn = document.getElementById('btnSend');
        btn.disabled = true;
        btn.innerHTML = '<span class="btn-icon">⏳</span> Sending...';

        const result = await fetchAPI(`/leads/${currentLead.id}/send`, {
            method: 'POST',
            body: JSON.stringify({ subject, body })
        });

        showToast('Email sent!', 'success');
        document.getElementById('modalStatus').textContent = formatStep(result.sequence_step);

        btn.disabled = false;
        btn.innerHTML = '<span class="btn-icon">📤</span> Send Email';

        loadLeads();
        updateStats();

    } catch (error) {
        const btn = document.getElementById('btnSend');
        btn.disabled = false;
        btn.innerHTML = '<span class="btn-icon">📤</span> Send Email';
    }
}

// Filters
function applyFilters() {
    pagination.page = 1; // Reset to page 1 on filter change
    loadLeads();
}

// Pagination functions
function handlePageSizeChange() {
    pagination.pageSize = parseInt(document.getElementById('pageSize').value);
    pagination.page = 1;
    loadLeads();
}

function goToPage(page) {
    if (page < 1 || page > pagination.totalPages) return;
    pagination.page = page;
    loadLeads();
}

function updatePaginationControls() {
    const start = ((pagination.page - 1) * pagination.pageSize) + 1;
    const end = Math.min(pagination.page * pagination.pageSize, pagination.total);

    document.getElementById('paginationInfo').textContent =
        pagination.total > 0 ? `Showing ${start}-${end} of ${pagination.total} leads` : 'No leads';
    document.getElementById('currentPage').textContent = pagination.page;
    document.getElementById('totalPages').textContent = pagination.totalPages;

    document.getElementById('btnPrevPage').disabled = !pagination.hasPrev;
    document.getElementById('btnNextPage').disabled = !pagination.hasNext;
}

// Update header stats
function updateHeaderStats(status) {
    document.getElementById('totalLeads').textContent = status.leads_count;
    document.getElementById('emailsToday').textContent = status.emails_sent_today;
    document.getElementById('quotaRemaining').textContent = status.emails_remaining_today;
}

// Utilities
function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

function truncate(str, len) {
    if (!str) return '';
    return str.length > len ? str.substring(0, len) + '...' : str;
}

function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

function showToast(message, type = 'info') {
    const container = document.getElementById('toastContainer');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;

    container.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = '0';
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

// Make openLeadModal global for onclick
window.openLeadModal = openLeadModal;
