import { navigate, store, authFetch } from '../main';
import { Navbar } from '../components/navbar';
import { io } from 'socket.io-client';

export function renderAnalysis(container) {
    const state = history.state || {};
    const analysisId = state.id || new URLSearchParams(location.search).get('id');

    if (!analysisId) {
        navigate('/dashboard');
        return;
    }

    container.innerHTML = '';
    container.appendChild(Navbar());

    const content = document.createElement('div');
    content.className = 'page-container';

    content.innerHTML = `
        <div class="ops-dashboard">
            <!-- Header Bar -->
            <div class="ops-header">
                <div class="ops-header-left">
                    <div class="ops-title">OPERATION #${String(analysisId).padStart(4, '0')}</div>
                    <div class="ops-subtitle">MULTI-AGENT PIPELINE EXECUTION</div>
                </div>
                <div class="ops-header-right">
                    <div id="status-badge" class="ops-status-badge processing">
                        <span class="status-dot"></span>
                        INITIALIZING
                    </div>
                </div>
            </div>

            <section id="dated-comparison" class="dated-comparison" hidden aria-label="Satellite image comparison">
                <h2>Historical and current imagery</h2>
                <p id="comparison-description" class="comparison-note"></p>
                <div class="comparison-grid">
                    <article class="comparison-card" id="historical-card">
                        <h3>Selected historical period</h3>
                        <p class="period-label"></p>
                        <div class="comparison-picture"><p>Waiting for satellite imagery…</p></div>
                        <p class="coverage-label"></p>
                        <a class="image-link" target="_blank" rel="noopener" hidden>Open full-size image ↗</a>
                    </article>
                    <article class="comparison-card" id="current-card">
                        <h3>Current comparison period</h3>
                        <p class="period-label"></p>
                        <div class="comparison-picture"><p>Waiting for satellite imagery…</p></div>
                        <p class="coverage-label"></p>
                        <a class="image-link" target="_blank" rel="noopener" hidden>Open full-size image ↗</a>
                    </article>
                </div>
                <div id="vegetation-summary" class="comparison-metrics" role="status">Vegetation comparison will appear after both images load.</div>
                <p id="comparison-message" class="comparison-note" role="status"></p>
                <p class="comparison-note">These are dated composites, not live photographs. Checkerboard pixels have no usable observations. Seasonal growth, harvests, water and soil can affect vegetation readings.</p>
            </section>
            <!-- Progress Panel -->
            <div class="ops-panel mb-2">
                <div class="ops-panel-header">
                    <div class="panel-title">MISSION PROGRESS</div>
                    <div id="progress-text" class="progress-percentage">0%</div>
                </div>
                <div class="progress-container">
                    <div id="progress-bar" class="progress-fill"></div>
                </div>
                <div id="current-stage" class="progress-stage">Awaiting agent initialization...</div>
            </div>

            <!-- Main Grid -->
            <div class="ops-analysis-grid">
                <!-- Activity Feed -->
                <div class="ops-panel">
                    <div class="ops-panel-header">
                        <div class="panel-title">AGENT ACTIVITY STREAM</div>
                        <div class="activity-indicator">
                            <span class="pulse-dot"></span>
                            LIVE
                        </div>
                    </div>
                    <div id="activity-log" class="activity-feed">
                        <!-- Logs appear here -->
                    </div>
                </div>
                
                <!-- Agent Pipeline -->
                <div class="ops-panel">
                    <div class="ops-panel-header">
                        <div class="panel-title">AGENT STATUS</div>
                    </div>
                    <div class="agent-pipeline" id="agent-status-list">
                        <div class="pipeline-agent" id="agent-imagery" data-agent="imagery">
                            <div class="agent-indicator idle"></div>
                            <div class="agent-info">
                                <div class="agent-name">IMAGERY-AGENT</div>
                                <div class="agent-activity">Idle</div>
                            </div>
                        </div>
                        <div class="pipeline-agent" id="agent-detect" data-agent="detect">
                            <div class="agent-indicator idle"></div>
                            <div class="agent-info">
                                <div class="agent-name">CHANGE-DETECT</div>
                                <div class="agent-activity">Idle</div>
                            </div>
                        </div>
                        <div class="pipeline-agent" id="agent-class" data-agent="class">
                            <div class="agent-indicator idle"></div>
                            <div class="agent-info">
                                <div class="agent-name">CLASSIFICATION</div>
                                <div class="agent-activity">Idle</div>
                            </div>
                        </div>
                        <div class="pipeline-agent" id="agent-invest" data-agent="invest">
                            <div class="agent-indicator idle"></div>
                            <div class="agent-info">
                                <div class="agent-name">INVESTIGATION</div>
                                <div class="agent-activity">Idle</div>
                            </div>
                        </div>
                        <div class="pipeline-agent" id="agent-report" data-agent="report">
                            <div class="agent-indicator idle"></div>
                            <div class="agent-info">
                                <div class="agent-name">REPORTING</div>
                                <div class="agent-activity">Idle</div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            
            <div id="report-btn-container" style="margin-top: 24px;"></div>
        </div>
    `;
    container.appendChild(content);

    const socket = io({ auth: { token: localStorage.getItem('token') } });
    let stopped = false;
    let lastLogCount = 0;
    const nodes = {
        badge: content.querySelector('#status-badge'),
        stage: content.querySelector('#current-stage'),
        progress: content.querySelector('#progress-bar'),
        percent: content.querySelector('#progress-text'),
        logs: content.querySelector('#activity-log'),
        actions: content.querySelector('#report-btn-container'),
    };
    const names = ['Imagery', 'Detection', 'Classification', 'Investigation', 'Reporting'];
    const ids = ['imagery', 'detect', 'class', 'invest', 'report'];
    function renderComparison(comparison) {
        if (!comparison) return;
        content.querySelector('#dated-comparison').hidden = false;
        content.querySelector('.ops-subtitle').textContent = 'SATELLITE DATE COMPARISON';
        content.querySelector('#comparison-description').textContent =
            `${comparison.mode === 'latest' ? 'Selected date vs latest available imagery' : 'Two dates you chose'} · Matching ${comparison.windowDays}-day windows, with no overlapping observations.`;
        for (const side of ['historical', 'current']) {
            const period = comparison[side];
            const card = content.querySelector(`#${side}-card`);
            card.querySelector('.period-label').textContent = `${period.startDate} through ${period.throughDate}`;
            const picture = card.querySelector('.comparison-picture');
            const link = card.querySelector('.image-link');
            if (period.imageUrl && picture.dataset.url !== period.imageUrl) {
                const img = new Image();
                img.alt = `${side === 'historical' ? 'Historical' : 'Later'} satellite image, ${period.startDate} through ${period.throughDate}`;
                img.src = period.imageUrl;
                img.onerror = () => { picture.textContent = 'Image could not load. Use the full-size link to retry.'; };
                picture.replaceChildren(img);
                picture.dataset.url = period.imageUrl;
                link.href = period.imageUrl;
                link.hidden = false;
            } else if (period.state === 'unavailable') {
                picture.textContent = period.error || 'No usable imagery in this period.';
            }
            card.querySelector('.coverage-label').textContent = period.coveragePercent != null
                ? `~${period.coveragePercent}% usable coverage · ${period.imageCount} scenes${period.readyForAnalysis ? '' : ' · Partial coverage'} · Source detail: ${period.sourceResolutionMeters || 10} m/pixel`
                : period.state === 'unavailable' ? 'Coverage unavailable' : 'Checking coverage…';
        }
        const metrics = comparison.metrics;
        const summary = content.querySelector('#vegetation-summary');
        if (metrics && metrics.ndviChange != null && metrics.commonCoveragePercent > 0) {
            const change = metrics.ndviChange;
            summary.textContent = `Vegetation index (NDVI): ${metrics.historicalNdvi.toFixed(3)} → ${metrics.currentNdvi.toFixed(3)}. Change: ${change > 0 ? '+' : ''}${change.toFixed(3)}. `
                + `Measured only over the ~${metrics.commonCoveragePercent}% of this region with usable data in both periods. `
                + 'Higher NDVI generally indicates greener vegetation; this is not proof of environmental damage.';
        } else if (metrics) {
            summary.textContent = 'No common usable pixels: a vegetation change cannot be measured for these periods.';
        } else if (comparison.metricsError) {
            summary.textContent = comparison.metricsError;
        } else if (comparison.aiStatus === 'unavailable') {
            summary.textContent = 'Both periods need usable imagery to measure vegetation change.';
        }
        content.querySelector('#comparison-message').textContent = comparison.message || 'Loading the two observation periods…';
    }
    function show(data) {
        renderComparison(data.comparison);
        nodes.progress.style.width = `${data.progress || 0}%`;
        nodes.percent.textContent = `${data.progress || 0}%`;
        nodes.badge.textContent = data.status.replaceAll('_', ' ').toUpperCase();
        nodes.badge.className = `ops-status-badge ${['completed', 'comparison_ready'].includes(data.status) ? 'completed' : data.status === 'failed' ? 'failed' : 'processing'}`;
        nodes.stage.textContent = data.error || data.comparison?.message || (data.status === 'completed' ? 'Report ready' : data.current_agent || 'Queued');
        const active = names.findIndex(n => (data.current_agent || '').includes(n));
        ids.forEach((id, i) => {
            const el = content.querySelector(`#agent-${id}`);
            const state = data.status === 'comparison_ready' ? (i === 0 ? 'Done' : 'Not run') : data.status === 'completed' || i < active ? 'Done' : i === active ? (data.status === 'failed' ? 'Failed' : 'Working') : 'Idle';
            el.querySelector('.agent-activity').textContent = state;
            el.querySelector('.agent-indicator').className = `agent-indicator ${state === 'Working' ? 'active' : 'idle'}`;
        });
        const logs = data.logs || [];
        logs.slice(lastLogCount).forEach(log => {
            const row = document.createElement('div');
            row.className = 'log-entry';
            row.textContent = `${log.agent}: ${log.message}`;
            if (log.status === 'error') row.style.color = 'var(--error)';
            nodes.logs.appendChild(row);
        });
        lastLogCount = logs.length;
        if (data.status === 'completed' && !nodes.actions.childElementCount) {
            const button = document.createElement('button');
            button.className = 'action-btn primary'; button.textContent = 'View report';
            button.onclick = () => navigate('/report', { id: analysisId });
            nodes.actions.appendChild(button);
        }
    }
    async function refresh() {
        if (stopped) return;
        try {
            const res = await authFetch(`/api/analysis/${analysisId}`);
            const data = await res.json();
            if (stopped) return;
            if (!res.ok) throw new Error(data.error || 'Unable to load analysis');
            show(data);
        } catch (err) {
            if (!stopped) nodes.stage.textContent = err.message;
        }
    }
    for (const event of ['analysis_progress', 'analysis_complete', 'analysis_failed']) {
        socket.on(event, data => { if (Number(data.analysis_id) === Number(analysisId)) refresh(); });
    }
    const timer = setInterval(refresh, 2500);
    store.pageCleanup = () => { stopped = true; clearInterval(timer); socket.disconnect(); };
    refresh();
}
