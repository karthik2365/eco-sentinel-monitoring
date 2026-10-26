import { navigate, store, authFetch } from '../main';
import { Navbar } from '../components/navbar';
import { io } from 'socket.io-client';

const escapeHTML = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

// Agent name mapping
const agentMap = {
  // New Professional Names
  'Imagery Acquisition Analyst': 'imagery',
  'Change Detection Specialist': 'detection',
  'Environmental Classification Officer': 'classification',
  'Strategic Investigation Unit': 'investigation',
  'Intelligence Reporting Officer': 'reporting',

  // Legacy/Fallback mapping
  'imagery': 'imagery',
  'detection': 'detection',
  'classification': 'classification',
  'investigation': 'investigation',
  'reporting': 'reporting',
  'ImageryAgent': 'imagery',
  'DetectionAgent': 'detection',
  'ClassificationAgent': 'classification',
  'InvestigationAgent': 'investigation',
  'ReportingAgent': 'reporting',

  // Specific stage names from orchestrator events if they differ
  'Imagery Acquisition': 'imagery',
  'Change Detection': 'detection',
  'Incident Classification': 'classification',
  'Investigation': 'investigation',
  'Report Generation': 'reporting'
};

export async function renderDashboard(container) {
  if (store.dashboardCleanup) { store.dashboardCleanup(); store.dashboardCleanup = null; }
  container.innerHTML = '';
  container.appendChild(Navbar());

  const content = document.createElement('div');
  content.className = 'page-container';

  // Fetch Metrics
  let metrics = { active_monitoring: 0, analyses_completed: 0, incidents_detected: 0, recent_analyses: [] };
  try {
    const res = await authFetch('/api/dashboard/metrics');
    if (res.ok) metrics = await res.json();
  } catch (e) { console.error(e); }

  if (location.pathname !== '/dashboard') return;
  content.innerHTML = `
        <div class="ops-dashboard">
            <!-- Header Bar -->
            <div class="ops-header">
                <div class="ops-header-left">
                    <div class="ops-title">INTELLIGENCE OPERATIONS</div>
                    <div class="ops-subtitle">AUTONOMOUS MONITORING SYSTEM</div>
                </div>
                <div class="ops-header-right">
                    <div class="system-status">
                        <div class="status-indicator pulse"></div>
                        <span>SYSTEM OPERATIONAL</span>
                    </div>
                    <button id="btn-new-analysis" class="ops-btn-primary">
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <line x1="12" y1="5" x2="12" y2="19"></line>
                            <line x1="5" y1="12" x2="19" y2="12"></line>
                        </svg>
                        INITIATE OPERATION
                    </button>
                </div>
            </div>

            <!-- Dashboard Grid: Metrics + Agent Status -->
            <div class="dashboard-grid">
                <!-- Left: Metrics 2x2 Grid -->
                <div class="ops-metrics-grid">
                    <div class="metric-box">
                        <div class="metric-label">ACTIVE SURVEILLANCE ZONES</div>
                        <div class="metric-value">${String(metrics.active_monitoring).padStart(3, '0')}</div>
                    </div>
                    <div class="metric-box">
                        <div class="metric-label">COMPLETED OPERATIONS</div>
                        <div class="metric-value">${String(metrics.analyses_completed).padStart(3, '0')}</div>
                    </div>
                    <div class="metric-box">
                        <div class="metric-label">THREAT DETECTIONS</div>
                        <div class="metric-value critical">${String(metrics.incidents_detected).padStart(3, '0')}</div>
                    </div>
                    <div class="metric-box">
                        <div class="metric-label">NETWORK STATUS</div>
                        <div class="metric-value">
                            <span class="status-text online">ONLINE</span>
                        </div>
                        <div class="metric-sublabel">Last sync: ${new Date().toLocaleTimeString()}</div>
                    </div>
                </div>

                <!-- Right: Agent Status + Live Logs -->
                <div class="right-panel-column" style="display: flex; flex-direction: column; gap: 20px;">
                    <div class="agent-status-panel">
                        <div class="agent-panel-header">AGENT STATUS</div>
                        <div class="agent-list" id="agent-list">
                            <div class="agent-item" data-agent="imagery">
                                <div class="agent-indicator idle"></div>
                                <div class="agent-info">
                                    <div class="agent-name">IMAGERY ACQUISITION</div>
                                    <div class="agent-activity">Idle</div>
                                </div>
                            </div>
                            <div class="agent-item" data-agent="detection">
                                <div class="agent-indicator idle"></div>
                                <div class="agent-info">
                                    <div class="agent-name">CHANGE DETECTION</div>
                                    <div class="agent-activity">Idle</div>
                                </div>
                            </div>
                            <div class="agent-item" data-agent="classification">
                                <div class="agent-indicator idle"></div>
                                <div class="agent-info">
                                    <div class="agent-name">CLASSIFICATION</div>
                                    <div class="agent-activity">Idle</div>
                                </div>
                            </div>
                            <div class="agent-item" data-agent="investigation">
                                <div class="agent-indicator idle"></div>
                                <div class="agent-info">
                                    <div class="agent-name">INVESTIGATION UNIT</div>
                                    <div class="agent-activity">Idle</div>
                                </div>
                            </div>
                            <div class="agent-item" data-agent="reporting">
                                <div class="agent-indicator idle"></div>
                                <div class="agent-info">
                                    <div class="agent-name">INTELLIGENCE REPORTING</div>
                                    <div class="agent-activity">Idle</div>
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- LIVE LOGS PANEL -->
                    <div class="live-logs-panel" style="background: linear-gradient(135deg, var(--bg-secondary) 0%, var(--bg-primary) 100%); border: 1px solid var(--border); border-radius: var(--radius-md); padding: 20px; flex: 1; display: flex; flex-direction: column; min-height: 250px;">
                         <div class="agent-panel-header" style="margin-bottom: 10px;">LIVE INTELLIGENCE FEED</div>
                         <div class="logs-container" id="logs-container" style="flex: 1; overflow-y: auto; max-height: 250px; font-family: var(--font-mono); font-size: 11px; color: var(--text-secondary); scrollbar-width: thin; scroll-behavior: smooth;">
                             <div class="log-entry" style="padding: 6px 0; border-bottom: 1px solid rgba(255,255,255,0.05); color: var(--text-muted);">
                                <span style="opacity: 0.5; margin-right: 8px;">${new Date().toLocaleTimeString().split(' ')[0]}</span>
                                <span style="color: var(--accent-cyan)">[SYSTEM]</span> Awaiting operation initiation...
                             </div>
                         </div>
                    </div>
                </div>
            </div>

            <!-- Operations Table -->
            <div class="ops-panel">
                <div class="ops-panel-header">
                    <div class="panel-title">OPERATION REGISTRY</div>
                    <div class="panel-controls">
                        <button class="filter-chip active">ALL</button>
                        <button class="filter-chip">ACTIVE</button>
                        <button class="filter-chip">FINISHED</button>
                    </div>
                </div>
                <div class="ops-table-container">
                    <table class="ops-table">
                        <thead>
                            <tr>
                                <th>OP-ID</th>
                                <th>TARGET DESIGNATION</th>
                                <th>TIMESTAMP</th>
                                <th>STATUS</th>
                                <th>ACTIONS</th>
                                <th></th>
                            </tr>
                        </thead>
                        <tbody>
                            ${metrics.recent_analyses.length === 0 ? `
                                <tr class="empty-state">
                                    <td colspan="6">
                                        <div class="empty-icon">◈</div>
                                        <div class="empty-text">NO ACTIVE OPERATIONS</div>
                                        <div class="empty-subtext">Initialize new operation to commence monitoring</div>
                                    </td>
                                </tr>
                            ` : metrics.recent_analyses.map(a => `
                                <tr class="ops-row" data-status="${a.status}">
                                    <td class="mono-text">OP-${String(a.id).padStart(4, '0')}</td>
                                    <td class="target-name">${escapeHTML(a.aoi_name)}</td>
                                    <td class="timestamp">${new Date(a.date).toLocaleDateString('en-US', { month: 'short', day: '2-digit', year: 'numeric' }).toUpperCase()}</td>
                                    <td>
                                        <span class="status-badge ${a.status}">
                                            <span class="status-dot"></span>
                                            ${a.status.replaceAll("_", " ").toUpperCase()}
                                        </span>
                                    </td>
                                    <td>
                                        <button class="ops-action-btn btn-view" data-id="${a.id}">
                                            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                                <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
                                                <circle cx="12" cy="12" r="3"></circle>
                                            </svg>
                                            ACCESS
                                        </button>
                                    </td>
                                    <td class="delete-column">
                                        <button class="ops-action-btn btn-delete" data-id="${a.id}">
                                            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                                <polyline points="3 6 5 6 21 6"></polyline>
                                                <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                                            </svg>
                                            DELETE
                                        </button>
                                    </td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    `;
  container.appendChild(content);
  const serviceBanner = document.createElement('div');
  serviceBanner.className = 'service-banner';
  serviceBanner.textContent = 'Checking satellite service…';
  content.prepend(serviceBanner);
  fetch('/health').then(r => r.json()).then(info => {
    serviceBanner.textContent = info.services.satellite === 'ready'
      ? 'Satellite connection ready. Live AI analysis requires a valid OpenRouter key.'
      : 'Satellite connection unavailable. Configure Google Earth Engine in backend/.env and restart. Saved reports remain available.';
  }).catch(() => { serviceBanner.textContent = 'Cannot reach the local backend.'; });

  content.querySelectorAll('.filter-chip').forEach(button => {
    button.onclick = () => {
      content.querySelectorAll('.filter-chip').forEach(b => b.classList.toggle('active', b === button));
      content.querySelectorAll('.ops-row').forEach(row => {
        const active = ['pending', 'in_progress'].includes(row.dataset.status);
        row.hidden = button.textContent === 'ACTIVE' ? !active : button.textContent === 'FINISHED' ? active : false;
      });
    };
  });
  // Restore active agent state if an analysis is in progress
  const activeAnalysis = metrics.recent_analyses.find(a => a.status === 'in_progress');
  if (activeAnalysis && activeAnalysis.current_agent && activeAnalysis.current_agent !== 'None') {
    const agentKey = agentMap[activeAnalysis.current_agent];
    if (agentKey) {
      updateAgentStatus(agentKey, true, "Resumed Operation...");
    }
  }

  content.querySelector('#btn-new-analysis').addEventListener('click', () => navigate('/map'));

  content.querySelectorAll('.btn-view').forEach(btn => {
    btn.addEventListener('click', async (e) => {
      const id = e.currentTarget.dataset.id;
      try {
        const res = await authFetch(`/api/analysis/${id}`);
        if (res.ok) {
          const analysis = await res.json();

          if (analysis.status === 'completed') {
            if (analysis.pdf_url) {
              // Open PDF in new tab
              navigate('/report', { id });
            } else {
              // Completed but no report found
              alert('Analysis complete, but report generation is pending or failed.');
              // Optional: valid fallback
              // navigate('/analysis', { id }); 
            }
          } else {
            // In progress or pending - go to live view
            navigate('/analysis', { id });
          }
        } else {
          navigate('/analysis', { id });
        }
      } catch (err) {
        console.error('Error fetching analysis:', err);
        navigate('/analysis', { id });
      }
    });
  });

  content.querySelectorAll('.btn-delete').forEach(btn => {
    btn.addEventListener('click', async (e) => {
      const id = e.currentTarget.dataset.id;
      const opId = `OP-${String(id).padStart(4, '0')}`;

      if (confirm(`CONFIRM OPERATION DELETION\n\nOperation ${opId} will be permanently removed from the registry.\n\nProceed with deletion?`)) {
        try {
          const res = await authFetch(`/api/analysis/${id}`, {
            method: 'DELETE',
            headers: { 'Content-Type': 'application/json' }
          });

          if (res.ok) {
            // Refresh the dashboard
            renderDashboard(container);
          } else {
            const error = await res.json();
            alert(`DELETION FAILED: ${error.message || 'Unknown error'}`);
          }
        } catch (err) {
          console.error('Delete error:', err);
          alert('NETWORK ERROR: Failed to delete operation');
        }
      }
    });
  });

  // Socket.IO connection for real-time agent status
  // Use polling first for Cloud Run compatibility (limited WebSocket support)
  const socket = io('/', {
    auth: { token: localStorage.getItem('token') },
    transports: ['polling', 'websocket'],
    reconnection: true,
    reconnectionAttempts: 5,
    reconnectionDelay: 1000,
    timeout: 20000
  });

  socket.on('connect', () => {
    addLog('Connected to real-time operations feed', 'success', 'SYSTEM');
  });

  socket.on('connect_error', (err) => {
    console.error('Socket connection error:', err);
    // Don't spam logs with connection errors in production
  });

  socket.on('disconnect', (reason) => {
    if (reason === 'io server disconnect') {
      // Server disconnected, try to reconnect
      socket.connect();
    }
  });

  const logsContainer = content.querySelector('#logs-container');

  function addLog(text, type = 'info', agent = null) {
    const div = document.createElement('div');
    div.className = 'log-entry';
    div.style.padding = '6px 0';
    div.style.borderBottom = '1px solid rgba(255,255,255,0.05)';
    div.style.animation = 'fadeIn 0.3s ease-in-out';

    const time = new Date().toLocaleTimeString().split(' ')[0];
    // Use upper case for agent in log
    const agentName = agent ? agent.toUpperCase() : 'SYSTEM';
    // Colorize agent name
    let color = 'var(--text-muted)';
    if (agentName.includes('IMAGERY')) color = '#60a5fa'; // Blue
    else if (agentName.includes('DETECTION')) color = '#f472b6'; // Pink
    else if (agentName.includes('CLASSIFICATION')) color = '#fbbf24'; // Yellow
    else if (agentName.includes('INVESTIGATION')) color = '#a78bfa'; // Purple
    else if (agentName.includes('REPORTING')) color = '#34d399'; // Green

    const agentSpan = agent ? `<span style="color: ${color}; font-weight: bold; margin-right: 6px;">[${agentName}]</span>` : `<span style="color: var(--text-muted); margin-right: 6px;">[SYSTEM]</span>`;

    div.innerHTML = `<span style="opacity: 0.4; margin-right: 8px; font-size: 10px;">${time}</span>${agentSpan}<span class="log-text"></span>`;
    div.querySelector('.log-text').textContent = text;

    // Highlights for text
    if (type === 'error') div.querySelector('.log-text').style.color = 'var(--error)';
    if (type === 'success') div.querySelector('.log-text').style.color = 'var(--success)';

    logsContainer.appendChild(div);
    // Smooth scroll to bottom
    setTimeout(() => {
      logsContainer.scrollTop = logsContainer.scrollHeight;
    }, 50);
  }

  // Function to update agent status
  function updateAgentStatus(agentKey, isActive, activity = null) {
    const agentItem = content.querySelector(`.agent-item[data-agent="${agentKey}"]`);
    if (agentItem) {
      const indicator = agentItem.querySelector('.agent-indicator');
      const activityEl = agentItem.querySelector('.agent-activity');

      if (isActive) {
        agentItem.classList.add('active');
        indicator.classList.remove('idle');
        indicator.classList.add('active');
        if (activity) activityEl.textContent = activity;
      } else {
        agentItem.classList.remove('active');
        indicator.classList.remove('active');
        indicator.classList.add('idle');
        activityEl.textContent = 'Idle';
      }
    }
  }

  // Reset all agents to idle
  function resetAllAgents() {
    ['imagery', 'detection', 'classification', 'investigation', 'reporting'].forEach(agent => {
      updateAgentStatus(agent, false);
    });
  }

  // === SOCKET EVENT LISTENERS ===

  // 1. Listen for detailed progress events
  socket.on('analysis_progress', (data) => {
    // data: { analysis_id, progress, current_stage }
    // current_stage now contains the professional agent name, e.g., "Imagery Acquisition Analyst"
    resetAllAgents();

    // Map the name to the ID
    const agentKey = agentMap[data.current_stage] || 'imagery';

    if (data.progress < 100) {
      updateAgentStatus(agentKey, true, `Processing...`);
    }

    if (data.progress === 100) {
      addLog(`Operation OP-${String(data.analysis_id).padStart(4, '0')} completed successfully.`, 'success', 'SYSTEM');
      resetAllAgents();
    }
  });

  // 2. Listen for agent logs
  socket.on('new_log', (data) => {
    // data: { timestamp, agent, message }
    addLog(data.message, 'info', data.agent);
  });

  // 3. Listen for reasoning (Thought process)
  socket.on('agent_reasoning', (data) => {
    // data: { agent_name, reasoning }
    const agentName = data.agent_name || 'SYSTEM';
    addLog(data.reasoning, 'info', agentName);

    const agentKey = agentMap[agentName];
    if (agentKey) {
      // Truncate for status display
      const snippet = data.reasoning.length > 40 ? data.reasoning.substring(0, 37) + "..." : data.reasoning;
      updateAgentStatus(agentKey, true, snippet);
    }
  });

  // 4. Listen for implicit agent status updates from base agent
  socket.on('agent_status', (data) => {
    // data: { agent_name, status, timestamp }
    const agentKey = agentMap[data.agent_name];
    if (agentKey) {
      if (data.status === 'working') {
        // Keep it active
        const agentItem = content.querySelector(`.agent-item[data-agent="${agentKey}"]`);
        if (agentItem && !agentItem.classList.contains('active')) {
          updateAgentStatus(agentKey, true, "Active");
        }
      }
      else if (data.status === 'failed') {
        updateAgentStatus(agentKey, true, 'FAILED');
        const agentItem = content.querySelector(`.agent-item[data-agent="${agentKey}"]`);
        if (agentItem) agentItem.querySelector('.agent-activity').style.color = 'var(--error)';
      }
    }
  });

  socket.on('analysis_failed', (data) => {
    addLog(`Operation failed: ${data.reason}`, 'error', 'SYSTEM');
    resetAllAgents();
    setTimeout(() => { if (location.pathname === '/dashboard') renderDashboard(container); }, 1500);
  });

  socket.on('analysis_complete', (data) => {
    setTimeout(() => {
      if (location.pathname === '/dashboard') renderDashboard(container);
    }, 2000);
  });

  // Cleanup socket on page change
  const cleanup = () => {
    socket.disconnect();
  };

  // Store cleanup function
  store.dashboardCleanup = cleanup;
}
