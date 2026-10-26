import { navigate, store } from '../main';
import Globe from 'globe.gl';
import * as THREE from 'three';

export function renderLogin(container) {
  container.innerHTML = `
    <div id="login-root">
      <div id="globe"></div>

      <div class="ui-overlay">

        <div class="login-panel">
          <div class="panel-header">
            <div class="logo">ECO-SENTINEL</div>
          </div>

          <form id="login-form" class="panel-body">

            <div class="field">
              <label>USERNAME</label>
              <input
                type="text"
                name="username"
                placeholder=""
                required
              />
            </div>

            <div class="field">
              <label>PASSWORD</label>
              <input
                type="password"
                name="password"
                placeholder="••••••••••"
                required
              />
            </div>

            <button type="submit" class="primary-btn">
              AUTHENTICATE
            </button>

            <div style="margin-top: 16px; text-align: center; font-size: 11px; color: rgba(255,255,255,0.4); font-family: monospace;">
              username = demo<br>
              password = demo123
            </div>
          </form>
        </div>
      </div>
    </div>
  `;

  bindLogin(container);
  try { initGlobe(); } catch (error) { console.warn("Globe background unavailable", error); }
}

/* ================================
   AUTH LOGIC (UNCHANGED)
================================ */
function bindLogin(container) {
  const form = container.querySelector('#login-form');

  form.addEventListener('submit', async (e) => {
    e.preventDefault();

    const btn = form.querySelector('button[type="submit"]');
    const originalText = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = 'AUTHENTICATING…';

    const formData = new FormData(form);
    const data = Object.fromEntries(formData.entries());

    try {
      const response = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
      });

      if (response.ok) {
        const result = await response.json();

        // Store JWT token and user
        localStorage.setItem('token', result.token);
        localStorage.setItem('user', JSON.stringify(result.user));
        store.user = result.user;

        navigate('/dashboard');
      } else {
        btn.disabled = false;
        btn.innerHTML = originalText;
        alert('Invalid credentials');
      }
    } catch (err) {
      console.error(err);
      btn.disabled = false;
      btn.innerHTML = originalText;
      alert('Connection error');
    }
  });
}

/* ================================
   GLOBE BACKGROUND
================================ */
function initGlobe() {
  const globe = new Globe(document.getElementById('globe'))
    .backgroundImageUrl(
      'https://unpkg.com/three-globe/example/img/night-sky.png'
    )
    .globeImageUrl(
      'https://unpkg.com/three-globe/example/img/earth-blue-marble.jpg'
    )
    .showAtmosphere(true)
    .atmosphereColor('#4aa3ff')
    .atmosphereAltitude(0.2)
    .enablePointerInteraction(false);

  // Base POV (India)
  const basePOV = { lat: 22, lng: 78, altitude: 2.2 };
  globe.pointOfView(basePOV, 0);

  // 🔴 HARD DISABLE drag / click rotation
  const controls = globe.controls();
  controls.enableRotate = false;
  controls.enableZoom = false;
  controls.enablePan = false;

  // Lighting
  const scene = globe.scene();
  scene.add(new THREE.AmbientLight(0xffffff, 1.2));

  const light = new THREE.DirectionalLight(0xffffff, 2.0);
  light.position.set(6, 5, 6);
  scene.add(light);

  // Extra light for satellites
  const satLight = new THREE.PointLight(0xffffff, 1.5, 300);
  satLight.position.set(50, 50, 50);
  scene.add(satLight);

  /* ================================
     SENTINEL-2 SATELLITES
  ================================ */
  const GLOBE_RADIUS = 100; // globe.gl default radius
  const ORBIT_ALTITUDE = 35; // altitude above globe surface
  const ORBIT_RADIUS = GLOBE_RADIUS + ORBIT_ALTITUDE;

  // Create realistic satellite geometry
  function createSatellite() {
    const satGroup = new THREE.Group();

    // Main body (gold-wrapped box) - brighter
    const bodyGeom = new THREE.BoxGeometry(3, 2, 4);
    const bodyMat = new THREE.MeshStandardMaterial({
      color: 0xffd700,
      metalness: 0.9,
      roughness: 0.1,
      emissive: 0x443300,
      emissiveIntensity: 0.3
    });
    const body = new THREE.Mesh(bodyGeom, bodyMat);
    satGroup.add(body);

    // Solar panels - brighter blue
    const panelGeom = new THREE.BoxGeometry(12, 0.2, 3);
    const panelMat = new THREE.MeshStandardMaterial({
      color: 0x2962ff,
      metalness: 0.6,
      roughness: 0.3,
      emissive: 0x0d47a1,
      emissiveIntensity: 0.2
    });

    // Left panel
    const leftPanel = new THREE.Mesh(panelGeom, panelMat);
    leftPanel.position.set(-7.5, 0, 0);
    satGroup.add(leftPanel);

    // Right panel
    const rightPanel = new THREE.Mesh(panelGeom, panelMat);
    rightPanel.position.set(7.5, 0, 0);
    satGroup.add(rightPanel);

    // Panel frame lines
    const frameMat = new THREE.MeshBasicMaterial({ color: 0x666666 });
    const frameGeom = new THREE.BoxGeometry(12, 0.3, 0.1);
    
    for (let i = -1; i <= 1; i++) {
      const frameLeft = new THREE.Mesh(frameGeom, frameMat);
      frameLeft.position.set(-7.5, 0.15, i * 1);
      satGroup.add(frameLeft);
      
      const frameRight = new THREE.Mesh(frameGeom, frameMat);
      frameRight.position.set(7.5, 0.15, i * 1);
      satGroup.add(frameRight);
    }

    // Antenna dish - brighter
    const dishGeom = new THREE.ConeGeometry(1.2, 1.5, 16, 1, true);
    const dishMat = new THREE.MeshStandardMaterial({
      color: 0xeeeeee,
      metalness: 0.95,
      roughness: 0.1,
      emissive: 0x444444,
      emissiveIntensity: 0.2,
      side: THREE.DoubleSide
    });
    const dish = new THREE.Mesh(dishGeom, dishMat);
    dish.rotation.x = Math.PI;
    dish.position.set(0, -1.8, 1.5);
    satGroup.add(dish);

    // Scale BIGGER for visibility
    satGroup.scale.set(0.35, 0.35, 0.35);

    return satGroup;
  }

  // Sentinel-2A (no orbit ring)
  const sat1 = createSatellite();
  scene.add(sat1);

  // Sentinel-2B (no orbit ring)
  const sat2 = createSatellite();
  scene.add(sat2);

  // Animation variables
  let angle1 = 0;
  let angle2 = Math.PI; // 180° offset for Sentinel-2B

  const ORBIT_SPEED = 0.003; // radians per frame
  const INCLINATION = THREE.MathUtils.degToRad(98.62);

  let stopped = false;
  function animateSatellites() {
    if (stopped) return;
    // Sentinel-2A position
    angle1 += ORBIT_SPEED;
    sat1.position.x = ORBIT_RADIUS * Math.cos(angle1);
    sat1.position.z = ORBIT_RADIUS * Math.sin(angle1) * Math.cos(INCLINATION);
    sat1.position.y = ORBIT_RADIUS * Math.sin(angle1) * Math.sin(INCLINATION);
    
    // Point satellite forward along orbit
    sat1.lookAt(
      ORBIT_RADIUS * Math.cos(angle1 + 0.1),
      ORBIT_RADIUS * Math.sin(angle1 + 0.1) * Math.sin(INCLINATION),
      ORBIT_RADIUS * Math.sin(angle1 + 0.1) * Math.cos(INCLINATION)
    );

    // Sentinel-2B position (180° offset)
    angle2 += ORBIT_SPEED;
    sat2.position.x = ORBIT_RADIUS * Math.cos(angle2);
    sat2.position.z = ORBIT_RADIUS * Math.sin(angle2) * Math.cos(INCLINATION);
    sat2.position.y = ORBIT_RADIUS * Math.sin(angle2) * Math.sin(INCLINATION);
    
    sat2.lookAt(
      ORBIT_RADIUS * Math.cos(angle2 + 0.1),
      ORBIT_RADIUS * Math.sin(angle2 + 0.1) * Math.sin(INCLINATION),
      ORBIT_RADIUS * Math.sin(angle2 + 0.1) * Math.cos(INCLINATION)
    );

    requestAnimationFrame(animateSatellites);
  }

  animateSatellites();

  /* ================================
     CURSOR-BASED ROTATION (KEY PART)
  ================================ */
  let targetLat = basePOV.lat;
  let targetLng = basePOV.lng;

  const ROTATE_X = 18;   // horizontal sensitivity
  const ROTATE_Y = 10;   // vertical sensitivity
  const SMOOTHING = 0.05;

  const moveCamera = (e) => {
    const x = (e.clientX / window.innerWidth - 0.5) * 2;
    const y = (e.clientY / window.innerHeight - 0.5) * 2;

    targetLng = basePOV.lng + x * ROTATE_X;
    targetLat = basePOV.lat - y * ROTATE_Y;
  };
  window.addEventListener("mousemove", moveCamera);
  store.pageCleanup = () => { stopped = true; window.removeEventListener("mousemove", moveCamera); globe.pauseAnimation(); globe.renderer().dispose(); };

  (function animateCamera() {
    if (stopped) return;
    const pov = globe.pointOfView();

    globe.pointOfView({
      lat: pov.lat + (targetLat - pov.lat) * SMOOTHING,
      lng: pov.lng + (targetLng - pov.lng) * SMOOTHING,
      altitude: pov.altitude
    });

    requestAnimationFrame(animateCamera);
  })();
}