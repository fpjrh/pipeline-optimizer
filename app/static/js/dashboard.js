let charts = {};

document.addEventListener('DOMContentLoaded', () => {
    loadRepos();
    loadDashboard();
    setupTabs();
    setupDarkMode();

    document.getElementById('repoFilter').addEventListener('change', loadDashboard);
    document.getElementById('daysFilter').addEventListener('change', loadDashboard);
    document.getElementById('collectBtn').addEventListener('click', collectData);
});

function getParams() {
    const repo = document.getElementById('repoFilter').value;
    const days = document.getElementById('daysFilter').value;
    let params = `days=${days}`;
    if (repo) params += `&repo=${encodeURIComponent(repo)}`;
    return params;
}

async function loadRepos() {
    try {
        const resp = await fetch('/api/repos');
        const repos = await resp.json();
        const select = document.getElementById('repoFilter');
        repos.forEach(r => {
            const opt = document.createElement('option');
            opt.value = r.full_name;
            opt.textContent = r.full_name;
            select.appendChild(opt);
        });
    } catch (e) {
        console.error('Failed to load repos:', e);
    }
}

async function loadDashboard() {
    const params = getParams();
    try {
        const [overview, costTrends, topWorkflows, runs] = await Promise.all([
            fetch(`/api/overview?${params}`).then(r => r.json()),
            fetch(`/api/cost-trends?${params}`).then(r => r.json()),
            fetch(`/api/top-workflows?${params}`).then(r => r.json()),
            fetch(`/api/runs?${params}`).then(r => r.json()),
        ]);
        updateOverviewCards(overview);
        updateCostTrendChart(costTrends);
        updateCostBreakdownChart(overview);
        updateDurationTrendChart(costTrends);
        updateTopWorkflowsChart(topWorkflows);
        updateRunsTable(runs);
        updateWorkflowTable(topWorkflows);
    } catch (e) {
        console.error('Failed to load dashboard:', e);
    }
}

function updateOverviewCards(data) {
    document.getElementById('total-runs').textContent = data.total_runs;
    document.getElementById('success-rate').textContent = data.success_rate + '%';
    document.getElementById('avg-duration').textContent = formatDuration(data.avg_duration_seconds);
    document.getElementById('total-cost').textContent = '$' + data.total_cost.toFixed(2);
    document.getElementById('compute-cost').textContent = '$' + data.total_compute_cost.toFixed(2);
    document.getElementById('llm-cost').textContent = '$' + data.total_llm_cost.toFixed(2);
    document.getElementById('llm-calls').textContent = data.total_llm_calls.toLocaleString();
    document.getElementById('total-tokens').textContent = formatTokens(data.total_tokens);
}

function updateCostTrendChart(data) {
    const ctx = document.getElementById('costTrendChart').getContext('2d');
    if (charts.costTrend) charts.costTrend.destroy();

    charts.costTrend = new Chart(ctx, {
        type: 'line',
        data: {
            labels: data.map(d => d.date),
            datasets: [
                {
                    label: 'Compute Cost',
                    data: data.map(d => d.compute_cost),
                    borderColor: '#667eea',
                    backgroundColor: 'rgba(102, 126, 234, 0.1)',
                    fill: true,
                    tension: 0.3,
                },
                {
                    label: 'LLM Cost',
                    data: data.map(d => d.llm_cost),
                    borderColor: '#f39c12',
                    backgroundColor: 'rgba(243, 156, 18, 0.1)',
                    fill: true,
                    tension: 0.3,
                },
            ],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { labels: { color: getTextColor() } },
                tooltip: {
                    callbacks: {
                        label: ctx => `${ctx.dataset.label}: $${ctx.parsed.y.toFixed(4)}`,
                    },
                },
            },
            scales: {
                x: { ticks: { color: getTextColor() }, grid: { color: getGridColor() } },
                y: {
                    ticks: { color: getTextColor(), callback: v => '$' + v.toFixed(2) },
                    grid: { color: getGridColor() },
                },
            },
        },
    });
}

function updateCostBreakdownChart(data) {
    const ctx = document.getElementById('costBreakdownChart').getContext('2d');
    if (charts.costBreakdown) charts.costBreakdown.destroy();

    charts.costBreakdown = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: ['Compute', 'LLM Tokens'],
            datasets: [{
                data: [data.total_compute_cost, data.total_llm_cost],
                backgroundColor: ['#667eea', '#f39c12'],
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { position: 'bottom', labels: { color: getTextColor() } },
                tooltip: {
                    callbacks: {
                        label: ctx => `${ctx.label}: $${ctx.parsed.toFixed(4)}`,
                    },
                },
            },
        },
    });
}

function updateDurationTrendChart(data) {
    const ctx = document.getElementById('durationTrendChart').getContext('2d');
    if (charts.durationTrend) charts.durationTrend.destroy();

    charts.durationTrend = new Chart(ctx, {
        type: 'line',
        data: {
            labels: data.map(d => d.date),
            datasets: [{
                label: 'Avg Duration (s)',
                data: data.map(d => d.avg_duration),
                borderColor: '#27ae60',
                backgroundColor: 'rgba(39, 174, 96, 0.1)',
                fill: true,
                tension: 0.3,
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { labels: { color: getTextColor() } },
            },
            scales: {
                x: { ticks: { color: getTextColor() }, grid: { color: getGridColor() } },
                y: {
                    ticks: { color: getTextColor(), callback: v => formatDuration(v) },
                    grid: { color: getGridColor() },
                },
            },
        },
    });
}

function updateTopWorkflowsChart(data) {
    const ctx = document.getElementById('topWorkflowsChart').getContext('2d');
    if (charts.topWorkflows) charts.topWorkflows.destroy();

    const top5 = data.slice(0, 5);
    charts.topWorkflows = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: top5.map(w => w.workflow.split('/').pop()),
            datasets: [{
                label: 'Total Cost ($)',
                data: top5.map(w => w.total_cost),
                backgroundColor: '#667eea',
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            indexAxis: 'y',
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: ctx => `$${ctx.parsed.x.toFixed(4)}`,
                        title: ctx => top5[ctx[0].dataIndex].workflow,
                    },
                },
            },
            scales: {
                x: {
                    ticks: { color: getTextColor(), callback: v => '$' + v.toFixed(2) },
                    grid: { color: getGridColor() },
                },
                y: { ticks: { color: getTextColor() }, grid: { display: false } },
            },
        },
    });
}

function updateRunsTable(runs) {
    const tbody = document.getElementById('runsTableBody');
    if (!runs.length) {
        tbody.innerHTML = '<tr><td colspan="7" class="no-data">No pipeline runs found. Click "Collect Data" to fetch from GitHub.</td></tr>';
        return;
    }
    tbody.innerHTML = runs.map(r => `
        <tr>
            <td>${escapeHtml(r.workflow_name)}</td>
            <td>${escapeHtml(r.repo_name)}</td>
            <td><span class="badge badge-${r.conclusion || 'cancelled'}">${r.conclusion || 'unknown'}</span></td>
            <td>${r.trigger_event || '-'}</td>
            <td>${formatDuration(r.duration_seconds)}</td>
            <td>$${r.total_cost.toFixed(4)}</td>
            <td>${r.started_at ? new Date(r.started_at).toLocaleDateString() : '-'}</td>
        </tr>
    `).join('');
}

function updateWorkflowTable(workflows) {
    const tbody = document.getElementById('workflowTableBody');
    if (!workflows.length) {
        tbody.innerHTML = '<tr><td colspan="5" class="no-data">No workflow data</td></tr>';
        return;
    }
    tbody.innerHTML = workflows.map(w => `
        <tr>
            <td>${escapeHtml(w.workflow)}</td>
            <td>${w.runs}</td>
            <td>${formatDuration(w.avg_duration)}</td>
            <td>${w.success_rate}%</td>
            <td>$${w.total_cost.toFixed(4)}</td>
        </tr>
    `).join('');
}

// LLM Usage tab
async function loadLLMUsage() {
    const params = getParams();
    try {
        const data = await fetch(`/api/llm-usage?${params}`).then(r => r.json());
        updateLLMCards(data);
        updateCostByModelChart(data);
        updateCostByPurposeChart(data);
        updateModelTable(data);
    } catch (e) {
        console.error('Failed to load LLM usage:', e);
    }
}

function updateLLMCards(data) {
    document.getElementById('llm-total-calls').textContent = data.total_calls.toLocaleString();
    document.getElementById('llm-total-tokens').textContent = formatTokens(data.total_tokens);
    document.getElementById('llm-total-cost').textContent = '$' + data.total_cost.toFixed(2);
}

function updateCostByModelChart(data) {
    const ctx = document.getElementById('costByModelChart').getContext('2d');
    if (charts.costByModel) charts.costByModel.destroy();

    const colors = ['#667eea', '#f39c12', '#27ae60', '#e74c3c', '#9b59b6', '#1abc9c', '#e67e22'];
    charts.costByModel = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: data.by_model.map(m => m.model),
            datasets: [{
                label: 'Cost ($)',
                data: data.by_model.map(m => m.cost),
                backgroundColor: data.by_model.map((_, i) => colors[i % colors.length]),
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: { label: ctx => `$${ctx.parsed.y.toFixed(4)} (${data.by_model[ctx.dataIndex].calls} calls)` },
                },
            },
            scales: {
                x: { ticks: { color: getTextColor(), maxRotation: 45 }, grid: { display: false } },
                y: { ticks: { color: getTextColor(), callback: v => '$' + v.toFixed(2) }, grid: { color: getGridColor() } },
            },
        },
    });
}

function updateCostByPurposeChart(data) {
    const ctx = document.getElementById('costByPurposeChart').getContext('2d');
    if (charts.costByPurpose) charts.costByPurpose.destroy();

    const colors = ['#667eea', '#f39c12', '#27ae60', '#e74c3c', '#9b59b6', '#1abc9c'];
    charts.costByPurpose = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: data.by_purpose.map(p => p.purpose),
            datasets: [{
                data: data.by_purpose.map(p => p.cost),
                backgroundColor: data.by_purpose.map((_, i) => colors[i % colors.length]),
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { position: 'bottom', labels: { color: getTextColor() } },
                tooltip: {
                    callbacks: { label: ctx => `${ctx.label}: $${ctx.parsed.toFixed(4)}` },
                },
            },
        },
    });
}

function updateModelTable(data) {
    const tbody = document.getElementById('modelTableBody');
    if (!data.by_model.length) {
        tbody.innerHTML = '<tr><td colspan="5" class="no-data">No LLM usage data</td></tr>';
        return;
    }
    tbody.innerHTML = data.by_model.map(m => `
        <tr>
            <td>${escapeHtml(m.model)}</td>
            <td>${m.calls.toLocaleString()}</td>
            <td>${formatTokens(m.tokens)}</td>
            <td>${m.avg_latency_ms ? m.avg_latency_ms + 'ms' : '-'}</td>
            <td>$${m.cost.toFixed(4)}</td>
        </tr>
    `).join('');
}

// Recommendations tab
async function loadRecommendations() {
    try {
        const recs = await fetch('/api/recommendations?status=new').then(r => r.json());
        const container = document.getElementById('recommendationsList');
        if (!recs.length) {
            container.innerHTML = '<p class="no-data">No active recommendations. Collect data and run the analyzer to generate suggestions.</p>';
            return;
        }
        container.innerHTML = recs.map(r => `
            <div class="recommendation priority-${r.priority}">
                <h3>
                    ${escapeHtml(r.title)}
                    <span class="category">${r.category}</span>
                </h3>
                <p>${escapeHtml(r.description)}</p>
                ${r.estimated_savings ? `<div class="savings">Estimated savings: ${escapeHtml(r.estimated_savings)}</div>` : ''}
                <div class="actions">
                    <button onclick="updateRecStatus(${r.id}, 'accepted')">Accept</button>
                    <button onclick="updateRecStatus(${r.id}, 'dismissed')">Dismiss</button>
                </div>
            </div>
        `).join('');
    } catch (e) {
        console.error('Failed to load recommendations:', e);
    }
}

async function updateRecStatus(id, status) {
    await fetch(`/api/recommendations/${id}/status?new_status=${status}`, { method: 'POST' });
    loadRecommendations();
}

// Data collection
async function collectData() {
    const btn = document.getElementById('collectBtn');
    btn.classList.add('collecting');
    btn.textContent = 'Collecting';
    try {
        const resp = await fetch('/api/collect', { method: 'POST' });
        const result = await resp.json();
        console.log('Collection result:', result);
        await loadDashboard();
        await loadRepos();
    } catch (e) {
        console.error('Collection failed:', e);
        alert('Data collection failed. Check your GitHub token and connection.');
    } finally {
        btn.classList.remove('collecting');
        btn.textContent = 'Collect Data';
    }
}

// Tab management
function setupTabs() {
    const savedTab = localStorage.getItem('po-active-tab') || 'overview';
    document.querySelectorAll('.tab-button').forEach(btn => {
        btn.addEventListener('click', () => switchTab(btn.dataset.tab));
    });
    switchTab(savedTab);
}

function switchTab(tabName) {
    document.querySelectorAll('.tab-button').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));

    const btn = document.querySelector(`.tab-button[data-tab="${tabName}"]`);
    const content = document.getElementById(`tab-${tabName}`);
    if (btn && content) {
        btn.classList.add('active');
        content.classList.add('active');
        localStorage.setItem('po-active-tab', tabName);

        if (tabName === 'llm-usage') loadLLMUsage();
        if (tabName === 'recommendations') loadRecommendations();
    }
}

// Dark mode
function setupDarkMode() {
    const saved = localStorage.getItem('po-dark-mode');
    if (saved === 'true') document.body.classList.add('dark-mode');

    document.getElementById('darkModeToggle').addEventListener('click', () => {
        document.body.classList.toggle('dark-mode');
        const isDark = document.body.classList.contains('dark-mode');
        localStorage.setItem('po-dark-mode', isDark);
        document.getElementById('darkModeToggle').textContent = isDark ? '☀️' : '🌙';
        Object.values(charts).forEach(c => {
            if (c && c.options) {
                c.update();
            }
        });
        loadDashboard();
    });
}

// Utilities
function formatDuration(seconds) {
    if (!seconds) return '-';
    if (seconds < 60) return seconds + 's';
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    if (m < 60) return `${m}m ${s}s`;
    const h = Math.floor(m / 60);
    return `${h}h ${m % 60}m`;
}

function formatTokens(count) {
    if (!count) return '0';
    if (count >= 1_000_000) return (count / 1_000_000).toFixed(1) + 'M';
    if (count >= 1_000) return (count / 1_000).toFixed(1) + 'K';
    return count.toLocaleString();
}

function getTextColor() {
    return document.body.classList.contains('dark-mode') ? '#b0b0b0' : '#666';
}

function getGridColor() {
    return document.body.classList.contains('dark-mode') ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.1)';
}

function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}
