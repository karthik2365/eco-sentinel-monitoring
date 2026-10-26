import { navigate, store, authFetch } from '../main';
import { Navbar } from '../components/navbar';

// Bundled Leaflet and drawing tools.
import L from '../map-library';

export function renderMap(container) {
    // Auth guard - redirect to login if no token
    if (!localStorage.getItem('token')) {
        navigate('/');
        return;
    }

    container.innerHTML = '';
    container.appendChild(Navbar());

    const wrapper = document.createElement('div');
    wrapper.className = 'map-wrapper';

    wrapper.innerHTML = `
    <div id="map"></div>
    
    <!-- HUD Panel -->
    <div class="control-bar">
        <div style="font-size: 13px; font-weight: 700; color: white; letter-spacing: 0.1em; margin-bottom: 8px;">MISSION CONTROL</div>
        
        <div class="control-group">
            <span class="control-label">Operation ID</span>
            <input type="text" id="aoi-name" placeholder="Enter codename..." class="control-input">
        </div>

        <div class="control-group">
            <label class="control-label" for="imageDate">Historical date</label>
            <input type="date" id="imageDate" value="${new Date(Date.now() - 29 * 86400000).toISOString().slice(0, 10)}" max="${new Date().toISOString().slice(0, 10)}" class="control-input">
        </div>
        
        <div class="control-group">
            <label class="control-label" for="comparisonMode">Compare with</label>
            <select id="comparisonMode" class="control-input" style="width:100%">
                <option value="latest">Latest available imagery</option>
                <option value="custom">Another date I choose</option>
            </select>
        </div>
        <div class="control-group" id="comparisonDateGroup" hidden>
            <label class="control-label" for="comparisonDate">Later comparison date</label>
            <input type="date" id="comparisonDate" value="${new Date().toISOString().slice(0, 10)}" max="${new Date().toISOString().slice(0, 10)}" class="control-input">
        </div>
        <div class="control-group">
            <span class="control-label">Preview spectrum</span>
            <div class="layer-toggle">
                <button class="layer-btn active" data-layer="rgb">RGB</button>
                <button class="layer-btn" data-layer="ndvi">NDVI</button>
            </div>
        </div>
        
        <div style="height: 10px;"></div>

        <button class="action-btn primary" id="generateBtn" disabled style="width: 100%; justify-content: center;">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>
            SCAN REGION
        </button>
        <button class="action-btn primary" id="compareBtn" disabled style="width:100%;justify-content:center">Start Analysis</button>
        <p id="comparisonHint" class="preview-quality">Compare the same region across two dates. Images remain available without an AI key.</p>
        <p id="comparisonError" role="alert" class="preview-quality" style="color:var(--error)"></p>
    </div>

    <div class="coords" id="coords">0.0000, 0.0000</div>
    <div class="area-info" id="areaInfo"></div>

    <!-- Preview Panel -->
    <div class="preview-panel" id="previewPanel">
        <div class="preview-header">
            <div class="preview-title">Satellite Preview <span class="preview-badge" id="imageCount">-</span></div>
            <button class="close-btn" id="closePreview">
                <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
            </button>
        </div>
        <div class="preview-body">
            <div class="preview-image" id="previewImage"><div class="spinner"></div></div>
            <p id="previewQuality" class="preview-quality" role="status"></p>
            <a id="fullPreview" class="full-preview" target="_blank" rel="noopener" hidden>Open full-size image ↗</a>
            <div class="preview-actions">
                 <button class="action-btn primary" id="startAnalysisBtn" disabled>
                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>
                    Start Analysis
                </button>
            </div>
        </div>
    </div>
    `;

    container.appendChild(wrapper);

    // --- Logic ---
    const map = L.map('map', { zoomControl: false, maxZoom: 16 }).setView([20.5937, 78.9629], 5);
    L.control.zoom({ position: 'bottomright' }).addTo(map);



    // Tiles
    const satellite = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', { attribution: ' Esri' }).addTo(map);
    const osm = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { attribution: ' OpenStreetMap' });
    const dark = L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', { attribution: ' CartoDB' });
    L.control.layers({ 'Satellite': satellite, 'Streets': osm, 'Dark': dark }, null, { position: 'topright' }).addTo(map);

    // Drawing
    const drawnItems = new L.FeatureGroup();
    map.addLayer(drawnItems);
    const drawControl = new L.Control.Draw({
        position: 'topright',
        draw: {
            polyline: false, circle: false, circlemarker: false, marker: false,
            rectangle: { shapeOptions: { color: '#6366f1', weight: 2, fillOpacity: 0.15 } },
            polygon: { allowIntersection: false, shapeOptions: { color: '#6366f1', weight: 2, fillOpacity: 0.15 } }
        },
        edit: { featureGroup: drawnItems, remove: true }
    });
    map.addControl(drawControl);

    // Variables
    let currentGeometry = null;
    let selectedLayer = 'rgb';
    let currentAreaKm2 = 0;
    let previewSelection = null;
    let startingComparison = false;
    let previewVersion = 0;
    let previewRequest = null;

    // Elements
    const generateBtn = document.getElementById('generateBtn');
    const previewPanel = document.getElementById('previewPanel');
    const previewImage = document.getElementById('previewImage');
    const imageCount = document.getElementById('imageCount');
    const coords = document.getElementById('coords');
    const areaInfo = document.getElementById('areaInfo');
    const startAnalysisBtn = document.getElementById('startAnalysisBtn');
    const closePreviewBtn = document.getElementById('closePreview');
    const aoiNameInput = document.getElementById('aoi-name');

    const compareBtn = document.getElementById('compareBtn');
    const comparisonMode = document.getElementById('comparisonMode');
    const comparisonDate = document.getElementById('comparisonDate');
    const comparisonError = document.getElementById('comparisonError');
    const previewQuality = document.getElementById('previewQuality');
    const fullPreview = document.getElementById('fullPreview');
    const scanLabel = generateBtn.innerHTML;
    function invalidatePreview() {
        previewVersion++;
        previewRequest?.abort();
        previewSelection = null;
        startAnalysisBtn.disabled = true;
        fullPreview.hidden = true;
        fullPreview.removeAttribute('href');
        previewPanel.classList.remove('visible');
        previewImage.classList.remove('has-imagery');
        generateBtn.innerHTML = scanLabel;
        generateBtn.disabled = !currentGeometry || areaInfo.classList.contains('error');
        compareBtn.disabled = generateBtn.disabled || startingComparison;
        comparisonError.textContent = '';
    }
    store.pageCleanup = () => { invalidatePreview(); map.remove(); };
    document.getElementById('imageDate').addEventListener('change', invalidatePreview);

    comparisonMode.addEventListener('change', () => {
        document.getElementById('comparisonDateGroup').hidden = comparisonMode.value !== 'custom';
        invalidatePreview();
    });
    comparisonDate.addEventListener('change', invalidatePreview);

    // Event Listeners
    document.querySelectorAll('.layer-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.layer-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            selectedLayer = btn.dataset.layer;
            invalidatePreview();
        });
    });

    map.on('mousemove', e => { coords.textContent = e.latlng.lat.toFixed(4) + ', ' + e.latlng.lng.toFixed(4); });

    function calculateArea(bounds) {
        const sw = bounds.getSouthWest();
        const ne = bounds.getNorthEast();
        const latDiff = Math.abs(ne.lat - sw.lat);
        const lngDiff = Math.abs(ne.lng - sw.lng);
        const avgLat = (sw.lat + ne.lat) / 2;
        // Approximate conversion
        const heightKm = latDiff * 111;
        const widthKm = lngDiff * 111 * Math.cos(avgLat * Math.PI / 180);
        return { area: heightKm * widthKm, widthKm, heightKm };
    }

    function getAreaStatus(areaKm2, widthKm, heightKm) {
        const minDim = Math.min(widthKm, heightKm);
        if (areaKm2 < 0.5 || minDim < 0.5) return { status: 'error', msg: 'Area too small (<0.5km)' };
        if (areaKm2 > 10000) return { status: 'warning', msg: 'Area large (>10k km²)' };
        return { status: 'good', msg: `${areaKm2.toFixed(1)} km² - Good` };
    }

    function updateSelection(layer) {
        const bounds = layer.getBounds();
        const { area, widthKm, heightKm } = calculateArea(bounds);
        const { status, msg } = getAreaStatus(area, widthKm, heightKm);
        currentAreaKm2 = area;
        currentGeometry = layer.toGeoJSON().geometry;
        areaInfo.textContent = msg;
        areaInfo.className = 'area-info visible ' + status;
        invalidatePreview();
    }
    map.on(L.Draw.Event.CREATED, e => {
        drawnItems.clearLayers();
        drawnItems.addLayer(e.layer);
        updateSelection(e.layer);
    });
    map.on(L.Draw.Event.EDITSTART, invalidatePreview);
    map.on(L.Draw.Event.EDITED, e => e.layers.eachLayer(updateSelection));
    map.on(L.Draw.Event.DELETED, () => {
        currentGeometry = null;
        areaInfo.className = 'area-info';
        invalidatePreview();
    });

    closePreviewBtn.addEventListener('click', () => { previewPanel.classList.remove('visible'); });

    // Generate Preview Handler
    generateBtn.addEventListener('click', async () => {
        if (!currentGeometry) return;

        invalidatePreview();
        const version = previewVersion;
        previewRequest = new AbortController();
        generateBtn.disabled = true;
        generateBtn.innerHTML = '<div class="spinner sm"></div>';
        previewPanel.classList.add('visible');
        previewImage.innerHTML = '<div class="loader-container"><div class="spinner"></div><div class="loader-text">Finding clear satellite pixels…</div></div>';
        imageCount.textContent = 'Checking coverage';
        previewQuality.textContent = 'Loading the selected historical period. Start Analysis will load both dates for comparison.';
        const selectedDate = document.getElementById('imageDate').value;
        const endDate = new Date(selectedDate);
        const startDate = new Date(endDate.getTime() - 29 * 86400000);
        const selection = { geometry: structuredClone(currentGeometry), area: currentAreaKm2 };
        function failed(message) {
            if (version !== previewVersion) return;
            previewImage.textContent = message;
            imageCount.textContent = 'Unavailable';
            previewQuality.textContent = 'Try another date or a smaller region.';
            generateBtn.disabled = false;
            generateBtn.innerHTML = scanLabel;
        }
        try {
            if (!Number.isFinite(endDate.getTime())) throw new Error('Choose a valid date.');
            const res = await authFetch('/api/map/preview', {
                method: 'POST', signal: previewRequest.signal,
                body: JSON.stringify({ geometry: selection.geometry,
                    startDate: startDate.toISOString().slice(0, 10),
                    endDate: new Date(endDate.getTime() + 86400000).toISOString().slice(0, 10), layerType: selectedLayer, expandWindow: false })
            });
            const data = await res.json();
            if (version !== previewVersion) return;
            if (!res.ok || !data.success) throw new Error(data.error || 'Preview failed.');
            imageCount.textContent = 'Rendering';
            const img = new Image();
            img.alt = `${selectedLayer.toUpperCase()} satellite composite, ${data.startDate} to ${data.endDate}`;
            img.onload = () => {
                if (version !== previewVersion) return;
                imageCount.textContent = `~${data.coveragePercent}% clear`;
                imageCount.classList.toggle('coverage-warning', !data.readyForAnalysis);
                previewQuality.textContent = `${data.imageCount} scenes · ${data.startDate} through ${new Date(new Date(data.endDate).getTime() - 86400000).toISOString().slice(0, 10)}. `
                    + (data.expandedWindow ? 'Date window expanded to fill cloud gaps. ' : '')
                    + (data.readyForAnalysis ? 'Clear-pixel composite; coverage is estimated. ' : 'Partial coverage: you can still open the dated comparison. ')
                    + 'Source detail: 10 m/pixel. Checkerboard areas have no usable pixels.';
                previewImage.replaceChildren(img);
                previewImage.classList.add('has-imagery');
                fullPreview.href = data.imageUrl;
                fullPreview.hidden = false;
                previewSelection = { ...selection, startDate: data.startDate, endDate: data.endDate };
                startAnalysisBtn.disabled = startingComparison;
                generateBtn.disabled = false;
                generateBtn.innerHTML = scanLabel;
            };
            img.onerror = () => failed('Could not load the satellite image. Scan again to retry.');
            img.src = data.imageUrl;
        } catch (err) {
            if (err.name !== 'AbortError') failed(err.message || 'Connection failed.');
        }
    });

    async function startComparison() {
        if (startingComparison || !currentGeometry) return;
        const historicalDate = document.getElementById('imageDate').value;
        const mode = comparisonMode.value;
        const later = mode === 'latest' ? new Date().toISOString().slice(0, 10) : comparisonDate.value;
        if (!historicalDate || !later || historicalDate >= later) {
            comparisonError.textContent = 'Choose a historical date earlier than the comparison date.';
            return;
        }
        const reviewed = { geometry: structuredClone(currentGeometry), area: currentAreaKm2 };
        const name = aoiNameInput.value.trim() || `Comparison ${historicalDate}`;
        startingComparison = true;
        compareBtn.disabled = startAnalysisBtn.disabled = true;
        compareBtn.textContent = 'Opening comparison…';
        comparisonError.textContent = '';
        try {
            const aoiRes = await authFetch('/api/map/aoi', {
                method: 'POST', body: JSON.stringify({ name, geometry: reviewed.geometry, area_km2: reviewed.area })
            });
            const aoiData = await aoiRes.json();
            if (!aoiRes.ok) throw new Error(aoiData.error || 'Could not save this region.');
            const res = await authFetch('/api/analysis/start', {
                method: 'POST', body: JSON.stringify({ aoi_id: aoiData.aoi.id,
                    comparison_mode: mode, historical_date: historicalDate,
                    comparison_date: mode === 'custom' ? later : undefined })
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.error || 'Could not start comparison.');
            navigate('/analysis', { id: data.analysis_id });
        } catch (err) {
            comparisonError.textContent = err.message;
            startingComparison = false;
            compareBtn.disabled = !currentGeometry;
            startAnalysisBtn.disabled = !previewSelection;
            compareBtn.textContent = 'Start Analysis';
        }
    }
    compareBtn.addEventListener('click', startComparison);
    startAnalysisBtn.addEventListener('click', startComparison);
}
