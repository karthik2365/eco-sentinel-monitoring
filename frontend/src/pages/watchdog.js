import { navigate, store, authFetch } from '../main';
import { Navbar } from '../components/navbar';

import L from '../map-library';

export function renderWatchdog(container) {
    // Auth guard
    if (!localStorage.getItem('token')) {
        navigate('/');
        return;
    }

    container.innerHTML = '';
    container.appendChild(Navbar());

    const wrapper = document.createElement('div');
    wrapper.className = 'map-wrapper';

    // Get today's date
    const today = new Date().toISOString().split('T')[0];

    wrapper.innerHTML = `
    <!-- Watchdog Setup Modal -->
    <div class="watchdog-modal" id="watchdogModal">
        <div class="watchdog-panel">
            <div class="watchdog-header">
                <div class="watchdog-icon">
                    <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                        <circle cx="12" cy="12" r="10"></circle>
                        <path d="M12 6v6l4 2"></path>
                    </svg>
                </div>
                <div class="watchdog-title">WATCHDOG MONITORING</div>
                <div class="watchdog-subtitle">Automated Daily Surveillance System</div>
            </div>
            
            <div class="watchdog-body">
                <div class="watchdog-field">
                    <label class="watchdog-label">SURVEILLANCE ZONE NAME</label>
                    <input type="text" id="watchdog-name" class="watchdog-input" placeholder="Enter zone designation">
                </div>
                
                <div class="watchdog-row">
                    <div class="watchdog-field">
                        <label class="watchdog-label">MONITORING START DATE</label>
                        <input type="date" id="watchdog-start" class="watchdog-input" value="${today}" readonly>
                        <span class="watchdog-hint">Starts from today</span>
                    </div>
                    
                    <div class="watchdog-field">
                        <label class="watchdog-label">CHECK FREQUENCY</label>
                        <select id="watchdog-frequency" class="watchdog-input">
                            <option value="daily">Daily</option>
                            <option value="weekly">Weekly</option>
                            <option value="biweekly">Bi-Weekly</option>
                        </select>
                    </div>
                </div>

                <div class="watchdog-field">
                    <label class="watchdog-label">ALERT THRESHOLD</label>
                    <select id="watchdog-threshold" class="watchdog-input">
                        <option value="any">Any Change Detected</option>
                        <option value="moderate">Medium Severity or Higher</option>
                        <option value="significant">High Severity or Higher</option>
                        <option value="critical">Critical Severity Only</option>
                    </select>
                </div>

                <div class="watchdog-info">
                    <div class="info-icon">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <circle cx="12" cy="12" r="10"></circle>
                            <line x1="12" y1="16" x2="12" y2="12"></line>
                            <line x1="12" y1="8" x2="12.01" y2="8"></line>
                        </svg>
                    </div>
                    <div class="info-text">
                        Select an area on the map to establish a monitoring zone. While this app is running, the system checks at the specified frequency. Findings appear here after each completed analysis. Satellite data may lag the current date.
                    </div>
                </div>
            </div>
            
            <div class="watchdog-footer">
                <button class="watchdog-cancel" id="watchdogCancel">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <line x1="18" y1="6" x2="6" y2="18"></line>
                        <line x1="6" y1="6" x2="18" y2="18"></line>
                    </svg>
                    Cancel
                </button>
                <button class="watchdog-proceed" id="watchdogProceed">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
                        <polyline points="22 4 12 14.01 9 11.01"></polyline>
                    </svg>
                    Proceed to Map
                </button>
            </div>
        </div>
    </div>

    <div id="map"></div>
    
    <!-- Floating Control Bar -->
    <div class="control-bar watchdog-control" id="controlBar" style="display: none;">
        <div class="watchdog-status">
            <div class="status-pulse"></div>
            <span>WATCHDOG MODE</span>
        </div>
        
        <div class="control-group">
            <span class="control-label" id="display-zone">Zone</span>
        </div>

        <div class="control-group">
            <span class="control-label">Start</span>
            <span class="control-value" id="display-date">${new Date().toLocaleDateString('en-US', { month: 'short', day: '2-digit', year: 'numeric' })}</span>
        </div>
        
        <div class="control-group">
            <span class="control-label">Frequency</span>
            <span class="control-value" id="display-freq">Daily</span>
        </div>
        
        <button class="action-btn" id="activateBtn" disabled>
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="10"></circle>
                <path d="M12 6v6l4 2"></path>
            </svg>
            Activate Watchdog
        </button>
    </div>

    <div class="coords" id="coords" style="display: none;">0.0000, 0.0000</div>
    <div class="area-info" id="areaInfo"></div>

    <!-- Confirmation Panel -->
    <div class="preview-panel watchdog-confirm" id="confirmPanel">
        <div class="preview-header">
            <div class="preview-title">Watchdog Configuration <span class="preview-badge" id="zoneStatus">Ready</span></div>
            <button class="close-btn" id="closeConfirm">
                <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
            </button>
        </div>
        <div class="preview-body">
            <div class="watchdog-summary" id="watchdogSummary">
                <div class="summary-item">
                    <span class="summary-label">Zone Area</span>
                    <span class="summary-value" id="summary-area">-</span>
                </div>
                <div class="summary-item">
                    <span class="summary-label">Frequency</span>
                    <span class="summary-value" id="summary-freq">Daily</span>
                </div>
                <div class="summary-item">
                    <span class="summary-label">Alert Threshold</span>
                    <span class="summary-value" id="summary-threshold">Any Change</span>
                </div>
                <div class="summary-item">
                    <span class="summary-label">First Check</span>
                    <span class="summary-value" id="summary-first">Today</span>
                </div>
            </div>
            <div class="preview-actions">
                <button class="action-btn primary" id="confirmWatchdog">
                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path>
                    </svg>
                    Activate Surveillance
                </button>
            </div>
        </div>
    </div>
    `;

    container.appendChild(wrapper);

    const schedules = document.createElement('div');
    schedules.className = 'watchdog-info';
    schedules.style.display = 'block';
    wrapper.querySelector('.watchdog-body').prepend(schedules);
    async function loadMonitors() {
        try {
            const response = await authFetch('/api/monitors');
            const data = await response.json();
            schedules.replaceChildren();
            const heading = document.createElement('strong'); heading.textContent = 'Saved monitoring zones'; schedules.appendChild(heading);
            if (!data.monitors?.length) {
                const empty = document.createElement('p'); empty.textContent = 'No schedules yet. Create one below.'; schedules.appendChild(empty);
            }
            for (const m of data.monitors || []) {
                const row = document.createElement('div'); row.style.marginTop = '12px';
                const text = document.createElement('p');
                text.textContent = `${m.name} · ${m.frequency} · ${m.active ? 'Next: ' + new Date(m.next_run).toLocaleString() : 'Paused'} · Last: ${m.last_status || 'none'}${m.alerts.length ? ' · Findings: ' + m.alerts.join(', ') : ''}`;
                row.appendChild(text);
                const toggle = document.createElement('button'); toggle.className = 'action-btn'; toggle.textContent = m.active ? 'Pause' : 'Resume';
                toggle.onclick = async () => {
                    const res = await authFetch(`/api/monitors/${m.id}`, {method:'PATCH', body:JSON.stringify({active:!m.active})});
                    if (res.ok) loadMonitors(); else alert('Could not update schedule');
                };
                row.appendChild(toggle);
                if (m.last_analysis_id) {
                    const view = document.createElement('button'); view.className = 'action-btn'; view.textContent = 'Latest check';
                    view.onclick = () => navigate('/analysis', {id:m.last_analysis_id}); row.appendChild(view);
                }
                schedules.appendChild(row);
            }
        } catch { schedules.textContent = 'Could not load saved schedules.'; }
    }
    loadMonitors();
    // --- Setup Modal Logic ---
    const modal = document.getElementById('watchdogModal');
    const proceedBtn = document.getElementById('watchdogProceed');
    const cancelBtn = document.getElementById('watchdogCancel');
    const controlBar = document.getElementById('controlBar');
    const coordsEl = document.getElementById('coords');
    const nameInput = document.getElementById('watchdog-name');
    const frequencySelect = document.getElementById('watchdog-frequency');
    const thresholdSelect = document.getElementById('watchdog-threshold');

    let zoneName = '';
    let frequency = 'daily';
    let threshold = 'any';

    cancelBtn.addEventListener('click', () => {
        navigate('/dashboard');
    });

    proceedBtn.addEventListener('click', () => {
        zoneName = nameInput.value.trim();
        frequency = frequencySelect.value;
        threshold = thresholdSelect.value;

        if (!zoneName) {
            nameInput.style.borderColor = '#d43d3d';
            nameInput.focus();
            return;
        }

        // Hide modal, show map controls
        modal.style.display = 'none';
        controlBar.style.display = 'flex';
        coordsEl.style.display = 'block';

        // Update display
        document.getElementById('display-zone').textContent = zoneName;
        document.getElementById('display-freq').textContent = frequency.charAt(0).toUpperCase() + frequency.slice(1);
        document.getElementById('summary-freq').textContent = frequency.charAt(0).toUpperCase() + frequency.slice(1);
        document.getElementById('summary-threshold').textContent = thresholdSelect.options[thresholdSelect.selectedIndex].text;

        initializeMap();
    });

    nameInput.addEventListener('input', () => {
        nameInput.style.borderColor = '';
    });

    // --- Map Initialization ---
    function initializeMap() {
        const map = L.map('map', { zoomControl: false, maxZoom: 16 }).setView([20.5937, 78.9629], 5);
        L.control.zoom({ position: 'bottomright' }).addTo(map);

        store.pageCleanup = () => map.remove();

        // Tiles
        const satellite = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', { attribution: ' Esri' }).addTo(map);
        const osm = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { attribution: ' OpenStreetMap' });
        const dark = L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', { attribution: ' CartoDB' });
        L.control.layers({ 'Satellite': satellite, 'Streets': osm, 'Dark': dark }, null, { position: 'topright' }).addTo(map);

        // Drawing
        const drawnItems = new L.FeatureGroup();
        map.addLayer(drawnItems);
        const drawControl = new L.Control.Draw({
            position: 'topleft',
            draw: {
                polyline: false, circle: false, circlemarker: false, marker: false,
                rectangle: { shapeOptions: { color: '#10b981', weight: 2, fillOpacity: 0.15 } },
                polygon: { allowIntersection: false, shapeOptions: { color: '#10b981', weight: 2, fillOpacity: 0.15 } }
            },
            edit: { featureGroup: drawnItems, remove: true }
        });
        map.addControl(drawControl);

        let currentGeometry = null;
        let currentAreaKm2 = 0;

        const activateBtn = document.getElementById('activateBtn');
        const confirmPanel = document.getElementById('confirmPanel');
        const areaInfo = document.getElementById('areaInfo');
        const closeConfirmBtn = document.getElementById('closeConfirm');
        const confirmWatchdogBtn = document.getElementById('confirmWatchdog');
        const coords = document.getElementById('coords');

        map.on('mousemove', e => { 
            coords.textContent = e.latlng.lat.toFixed(4) + ', ' + e.latlng.lng.toFixed(4); 
        });

        function calculateArea(bounds) {
            const sw = bounds.getSouthWest();
            const ne = bounds.getNorthEast();
            const latDiff = Math.abs(ne.lat - sw.lat);
            const lngDiff = Math.abs(ne.lng - sw.lng);
            const avgLat = (sw.lat + ne.lat) / 2;
            const heightKm = latDiff * 111;
            const widthKm = lngDiff * 111 * Math.cos(avgLat * Math.PI / 180);
            return { area: heightKm * widthKm, widthKm, heightKm };
        }

        function getAreaStatus(areaKm2, widthKm, heightKm) {
            const minDim = Math.min(widthKm, heightKm);
            if (areaKm2 < 0.5 || minDim < 0.5) return { status: 'error', msg: 'Area too small (<0.5km)' };
            if (areaKm2 > 10000) return { status: 'warning', msg: 'Area large (>10k km²)' };
            return { status: 'good', msg: `${areaKm2.toFixed(1)} km² - Valid` };
        }

        map.on(L.Draw.Event.CREATED, e => {
            drawnItems.clearLayers();
            drawnItems.addLayer(e.layer);

            const bounds = e.layer.getBounds();
            const { area, widthKm, heightKm } = calculateArea(bounds);
            const { status, msg } = getAreaStatus(area, widthKm, heightKm);

            currentAreaKm2 = area;
            areaInfo.textContent = msg;
            areaInfo.className = 'area-info visible ' + status;

            if (e.layerType === 'rectangle') {
                currentGeometry = { type: 'rectangle', coordinates: [[bounds.getSouthWest().lng, bounds.getSouthWest().lat], [bounds.getNorthEast().lng, bounds.getNorthEast().lat]] };
            } else if (e.layerType === 'polygon') {
                const c = e.layer.getLatLngs()[0].map(ll => [ll.lng, ll.lat]);
                c.push(c[0]);
                currentGeometry = { type: 'polygon', coordinates: c };
            }

            activateBtn.disabled = (status === 'error');
            document.getElementById('summary-area').textContent = `${area.toFixed(2)} km²`;
        });

        map.on(L.Draw.Event.DELETED, () => {
            currentGeometry = null;
            activateBtn.disabled = true;
            areaInfo.className = 'area-info';
        });

        closeConfirmBtn.addEventListener('click', () => { 
            confirmPanel.classList.remove('visible'); 
        });

        // Show confirmation panel
        activateBtn.addEventListener('click', () => {
            if (!currentGeometry) return;
            confirmPanel.classList.add('visible');
        });

        // Activate watchdog
        confirmWatchdogBtn.addEventListener('click', async () => {
            if (!zoneName || !currentGeometry) {
                alert('Please complete all fields and select an area');
                return;
            }

            try {
                confirmWatchdogBtn.disabled = true;
                confirmWatchdogBtn.innerHTML = 'Activating...';

                // 1. Create AOI for watchdog
                const aoiRes = await authFetch('/api/map/aoi', {
                    method: 'POST',
                    body: JSON.stringify({
                        name: `[WATCHDOG] ${zoneName}`,
                        geometry: currentGeometry,
                        area_km2: currentAreaKm2
                    })
                });
                const aoiData = await aoiRes.json();

                if (!aoiRes.ok) throw new Error(aoiData.error || 'Failed to create watchdog zone');

                // 2. Start initial analysis with today's date
                const today = new Date();
                const startDate = new Date(today);
                startDate.setDate(today.getDate() - 30); // Compare with 30 days ago

                const analyzeRes = await authFetch('/api/analysis/start', {
                    method: 'POST',
                    body: JSON.stringify({
                        aoi_id: aoiData.aoi.id,
                        start_date: startDate.toISOString().split('T')[0],
                        end_date: today.toISOString().split('T')[0],
                        analysis_type: 'watchdog',
                        frequency: frequency,
                        threshold: threshold
                    })
                });

                const analyzeData = await analyzeRes.json();
                if (!analyzeRes.ok) throw new Error(analyzeData.error || 'Failed to activate watchdog');

                // Navigate to dashboard
                navigate('/analysis', { id: analyzeData.analysis_id });

            } catch (err) {
                alert(err.message);
                confirmWatchdogBtn.disabled = false;
                confirmWatchdogBtn.innerHTML = `
                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path>
                    </svg>
                    Activate Surveillance
                `;
            }
        });
    }
}
