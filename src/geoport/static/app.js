const $ = (id) => document.getElementById(id);
const token = document.querySelector('meta[name="geoport-token"]').content;
let session = { status: 'disconnected', session_id: null };
let busy = false;
let revision = 0;
let lastError = '';
let routes = [];
let bookmarks = [];
let drawing = false;
let selectedPoint = null;
let map, selectedMarker, liveMarker, routeLayer;

function notice(message, error = false) {
  $('notice').textContent = message;
  $('notice').classList.toggle('error', error);
}

async function api(path, { method = 'GET', data, form } = {}) {
  const headers = { 'X-GeoPort-Token': token };
  if (data) headers['Content-Type'] = 'application/json';
  const response = await fetch(path, {
    method, headers, body: form || (data ? JSON.stringify(data) : undefined),
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result.error?.message || `Request failed (${response.status}).`);
  return result;
}

function updateControls() {
  const connected = Boolean(session.session_id);
  const playing = session.status === 'playing';
  const paused = session.status === 'paused';
  $('connect').disabled = busy || connected || !$('device').value;
  $('device').disabled = busy || connected;
  for (const id of ['disconnect', 'restore', 'wifi']) $(id).disabled = busy || !connected;
  $('simulate').disabled = busy || !connected;
  $('play').disabled = busy || !connected || playing || paused || !activeRoute()?.points?.length;
  $('pause').disabled = busy || !(playing || paused);
  $('pause').textContent = paused ? 'Resume' : 'Pause';
  for (const id of ['draw', 'clear-route', 'routes', 'import', 'speed', 'custom-speed']) {
    $(id).disabled = busy || playing || paused;
  }
  $('refresh').disabled = busy;
  $('status').textContent = busy ? 'Working…' : {
    disconnected: 'Disconnected', connecting: 'Connecting…', ready: 'Ready',
    simulating: 'Simulating', playing: 'Playing route', paused: 'Route paused', error: 'Connection lost',
  }[session.status] || session.status;
  $('status-dot').className = `status-dot ${connected ? 'active' : ''} ${session.error ? 'error' : ''}`;
  $('active-device').textContent = session.device
    ? `${session.device.name} · iOS ${session.device.ios}` : 'Connect a device to begin';
}

function applySession(result) {
  session = result;
  if (result.location) {
    const point = result.location;
    if (map) {
      if (!liveMarker) liveMarker = L.circleMarker(point, {
        radius: 7, color: '#fff', weight: 2, fillColor: '#d86745', fillOpacity: 1,
      }).addTo(map);
      liveMarker.setLatLng(point);
    }
    $('live-coordinates').textContent = point.map((n) => n.toFixed(5)).join(' / ');
  } else {
    if (liveMarker) { liveMarker.remove(); liveMarker = null; }
    $('live-coordinates').textContent = '—';
  }
  if (result.playback) {
    const { distance_m: distance, total_m: total, speed_kmh: speed } = result.playback;
    $('progress').value = distance / total;
    $('playback-detail').textContent = `${(distance / 1000).toFixed(2)} / ${(total / 1000).toFixed(2)} km · ${speed} km/h`;
  } else {
    $('progress').value = 0;
    $('playback-detail').textContent = 'Playback continues while this tab is in the background.';
  }
  const error = result.error?.message || '';
  if (error && error !== lastError) notice(error, true);
  lastError = error;
  updateControls();
}

async function command(path, data = {}, method = 'POST', message = '') {
  if (busy) return;
  busy = true;
  revision++;
  updateControls();
  try {
    const result = await api(path, { method, data: { ...data, session_id: session.session_id } });
    applySession(result);
    if (message) notice(message);
  } catch (error) {
    notice(error.message, true);
    try { applySession(await api('/api/session')); } catch { /* Poll will mark offline. */ }
  } finally {
    busy = false;
    updateControls();
  }
}

async function poll() {
  const started = revision;
  if (!busy) {
    try {
      const result = await api('/api/session');
      if (started === revision && !busy) applySession(result);
    } catch {
      if (started === revision && !busy) {
        session = { status: 'disconnected', session_id: null };
        updateControls();
        notice('GeoPort is unreachable. Check that it is still running on this computer.', true);
      }
    }
  }
  setTimeout(poll, 1000);
}

async function refreshDevices() {
  $('refresh').disabled = true;
  try {
    const { devices } = await api('/api/devices');
    const previous = $('device').value;
    $('device').replaceChildren();
    if (!devices.length) $('device').add(new Option('No devices found', ''));
    for (const device of devices) {
      const transports = device.transports.map((t) => t === 'Network' ? 'Wi-Fi' : t).join(' + ');
      const option = new Option(`${device.name} · ${transports} · iOS ${device.ios}`, device.id);
      option.title = device.problem || '';
      $('device').add(option);
    }
    if (devices.some((d) => d.id === previous)) $('device').value = previous;
    $('device-hint').textContent = devices.length
      ? 'Connect to pair and prepare developer services. This can take a minute.'
      : 'Unlock and connect by USB. For Wi-Fi, pair first and use the same local network.';
    const problems = devices.filter((d) => d.problem);
    if (problems.length) notice(`${problems.length} device(s) need attention. Unlock and select Connect to pair.`, true);
  } catch (error) {
    notice(error.message, true);
  } finally {
    updateControls();
  }
}

function readPoint() {
  const lat = $('latitude').value.trim(), lon = $('longitude').value.trim();
  if (!lat || !lon) throw new Error('Enter both latitude and longitude.');
  const point = [Number(lat), Number(lon)];
  if (!point.every(Number.isFinite) || Math.abs(point[0]) > 90 || Math.abs(point[1]) > 180) {
    throw new Error('Enter valid coordinates: latitude ±90, longitude ±180.');
  }
  return point;
}

function choosePoint(point, pan = false) {
  selectedPoint = point;
  $('latitude').value = point[0].toFixed(6);
  $('longitude').value = point[1].toFixed(6);
  if (!map) return;
  if (!selectedMarker) selectedMarker = L.circleMarker(point, {
    radius: 9, color: '#245b43', weight: 2, fillColor: '#fff', fillOpacity: 0.7,
  }).addTo(map);
  selectedMarker.setLatLng(point);
  if (pan) map.setView(point, Math.max(map.getZoom(), 13));
}

function activeRoute() { return routes[Number($('routes').value)]; }

function renderRouteOptions(selected = routes.length - 1) {
  $('routes').replaceChildren();
  routes.forEach((route, index) => $('routes').add(new Option(route.name, String(index))));
  if (!routes.length) $('routes').add(new Option('No routes yet', ''));
  else $('routes').value = String(selected);
  renderRoute();
}

function renderRoute(fit = false) {
  const route = activeRoute();
  if (map) {
    if (routeLayer) routeLayer.remove();
    routeLayer = route ? L.polyline(route.points, { color: '#d86745', weight: 3 }).addTo(map) : null;
    if (fit && route?.points.length > 1) map.fitBounds(routeLayer.getBounds(), { padding: [40, 40] });
  }
  $('route-hint').textContent = drawing ? 'Click the map to add points. Choose Finish drawing when ready.'
    : route ? `${route.points.length} points. Movement is interpolated between points.`
      : 'Draw a route or import a GPX / GeoJSON file.';
  updateControls();
}

function finishDrawing() {
  drawing = false;
  $('draw').textContent = 'Draw route';
  $('draw').classList.remove('drawing');
  renderRoute();
}

function initializeMap() {
  if (!window.L) {
    notice('Map assets could not load. You can still enter coordinates and simulate a location.', true);
    return;
  }
  map = L.map('map', { zoomControl: false }).setView([37.7749, -122.4194], 12);
  L.control.zoom({ position: 'topright' }).addTo(map);
  const tiles = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19, attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
  }).addTo(map);
  tiles.once('tileerror', () => notice('Map tiles are unavailable. Coordinate entry and device control still work.'));
  map.on('click', ({ latlng }) => {
    const point = [latlng.lat, ((latlng.lng + 180) % 360 + 360) % 360 - 180];
    choosePoint(point);
    if (drawing) { activeRoute().points.push(point); renderRoute(); }
  });
}

$('refresh').addEventListener('click', refreshDevices);
$('device').addEventListener('change', updateControls);
$('connect').addEventListener('click', () => {
  notice('Connecting… Unlock the device and accept any pairing prompt. Preparing its developer image may take a minute.');
  command('/api/connect', { device_id: $('device').value }, 'POST', 'Connected. Choose a location or play a route.');
});
$('disconnect').addEventListener('click', () => command('/api/disconnect', {}, 'POST', 'Restore GPS request sent. Device disconnected.'));
$('restore').addEventListener('click', () => command('/api/location', {}, 'DELETE', 'Restore GPS request sent. Route playback stopped.'));
$('wifi').addEventListener('click', () => command('/api/wifi', {}, 'POST',
  'Wi-Fi connections enabled. Disconnect here, unplug USB, then refresh and reconnect on the same Wi-Fi. The computer must stay running.'));
$('location-form').addEventListener('submit', (event) => {
  event.preventDefault();
  try {
    const point = readPoint();
    choosePoint(point);
    command('/api/location', { point }, 'POST', 'Location accepted by the device service.');
  } catch (error) { notice(error.message, true); }
});

let searchController;
$('search-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const query = $('search').value.trim();
  if (!query) return;
  const coords = query.split(',').map((part) => Number(part.trim()));
  if (query.includes(',') && coords.length === 2 && coords.every(Number.isFinite)
      && Math.abs(coords[0]) <= 90 && Math.abs(coords[1]) <= 180) {
    choosePoint(coords, true);
    return;
  }
  searchController?.abort();
  searchController = new AbortController();
  const controller = searchController;
  const timer = setTimeout(() => controller.abort(), 10000);
  $('search-results').textContent = 'Searching…';
  try {
    const response = await fetch(`https://nominatim.openstreetmap.org/search?format=json&limit=5&q=${encodeURIComponent(query)}`, { signal: controller.signal });
    if (!response.ok) throw new Error('Place search is unavailable. You can enter coordinates directly.');
    const results = await response.json();
    if (controller !== searchController) return;
    $('search-results').replaceChildren();
    if (!results.length) $('search-results').textContent = 'No places found.';
    for (const result of results) {
      const button = document.createElement('button');
      button.textContent = result.display_name;
      button.addEventListener('click', () => {
        choosePoint([Number(result.lat), Number(result.lon)], true);
        $('search-results').replaceChildren();
      });
      $('search-results').append(button);
    }
  } catch (error) {
    if (controller === searchController) {
      $('search-results').replaceChildren();
      notice(error.name === 'AbortError' ? 'Search timed out. Try coordinates instead.' : error.message, true);
    }
  } finally { clearTimeout(timer); }
});

$('draw').addEventListener('click', () => {
  if (drawing) { finishDrawing(); return; }
  drawing = true;
  routes.push({ name: `Drawn route ${routes.length + 1}`, points: [] });
  $('draw').textContent = 'Finish drawing';
  $('draw').classList.add('drawing');
  renderRouteOptions();
});
$('clear-route').addEventListener('click', () => {
  if (routes.length) routes.splice(Number($('routes').value), 1);
  finishDrawing(); renderRouteOptions();
});
$('routes').addEventListener('change', () => { finishDrawing(); renderRoute(true); });
$('speed').addEventListener('change', () => { $('custom-speed-label').hidden = $('speed').value !== 'custom'; });
$('play').addEventListener('click', () => {
  const route = activeRoute();
  if (!route || route.points.length < 2) { notice('Add at least two route points.', true); return; }
  const speed = Number($('speed').value === 'custom' ? $('custom-speed').value : $('speed').value);
  if (!Number.isFinite(speed) || speed <= 0 || speed > 999) {
    notice('Speed must be greater than 0 and no more than 999 km/h.', true); return;
  }
  finishDrawing();
  command('/api/playback', { points: route.points, speed_kmh: speed }, 'POST', 'Route playing. Restore GPS stops playback and clears simulation.');
});
$('pause').addEventListener('click', () => {
  const action = session.status === 'paused' ? 'resume' : 'pause';
  command(`/api/playback/${action}`, {}, 'POST', action === 'pause' ? 'Route paused at the last position.' : 'Route resumed.');
});

$('import').addEventListener('change', async (event) => {
  const file = event.target.files[0];
  if (!file) return;
  if (file.size > 5 * 1024 * 1024) { notice('Choose a file smaller than 5 MB.', true); return; }
  const form = new FormData(); form.append('file', file);
  try {
    const result = await api('/api/import', { method: 'POST', form });
    finishDrawing();
    routes.push(...result.routes);
    bookmarks.push(...result.markers);
    renderRouteOptions(); renderRoute(true);
    $('bookmarks').replaceChildren();
    for (const marker of bookmarks) {
      const button = document.createElement('button');
      button.textContent = marker.name;
      button.addEventListener('click', () => choosePoint(marker.point, true));
      $('bookmarks').append(button);
    }
    if (!result.routes.length && result.markers.length) choosePoint(result.markers[0].point, true);
    notice(`Imported ${result.routes.length} route(s) and ${result.markers.length} marker(s). GPX segments stay separate.`);
  } catch (error) { notice(error.message, true); }
  finally { event.target.value = ''; }
});
$('export').addEventListener('click', () => {
  const points = [...bookmarks];
  if (selectedPoint) points.push({ name: 'Selected location', point: selectedPoint });
  const features = [
    ...routes.filter((r) => r.points.length >= 2).map((r) => ({ type: 'Feature', properties: { name: r.name },
      geometry: { type: 'LineString', coordinates: r.points.map(([lat, lon]) => [lon, lat]) } })),
    ...points.map((m) => ({ type: 'Feature', properties: { name: m.name },
      geometry: { type: 'Point', coordinates: [m.point[1], m.point[0]] } })),
  ];
  if (!features.length) { notice('Choose a location or draw a route first.'); return; }
  const url = URL.createObjectURL(new Blob([JSON.stringify({ type: 'FeatureCollection', features }, null, 2)], { type: 'application/geo+json' }));
  const link = document.createElement('a'); link.href = url; link.download = 'geoport.geojson'; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
});

async function loadFuel() {
  $('fuel-results').textContent = 'Loading prices…';
  try {
    const { prices } = await api(`/api/fuel?region=${encodeURIComponent($('region').value)}`);
    $('fuel-results').replaceChildren();
    if (!prices.length) $('fuel-results').textContent = 'No prices for this region.';
    for (const price of prices) {
      const button = document.createElement('button');
      button.textContent = `${price.type} · ${price.price} · ${price.suburb}`;
      button.addEventListener('click', () => choosePoint([Number(price.lat), Number(price.lng)], true));
      $('fuel-results').append(button);
    }
  } catch (error) { $('fuel-results').textContent = error.message; }
}
$('fuel-panel').addEventListener('toggle', () => { if ($('fuel-panel').open) loadFuel(); });
$('region').addEventListener('change', loadFuel);
$('theme').addEventListener('click', () => {
  const dark = document.body.classList.toggle('dark');
  $('theme').textContent = dark ? 'Light mode' : 'Dark mode';
});
initializeMap();
refreshDevices();
poll();
