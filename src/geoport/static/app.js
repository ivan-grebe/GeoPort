import { RouteArrows } from './route-arrows.js';

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
let map, selectedMarker, liveMarker, routeLayer, routeArrows;
let routeNodes = [];

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
  for (const id of ['disconnect', 'restore']) $(id).disabled = busy || !connected;
  $('simulate').disabled = busy || !connected;
  $('play').disabled = busy || !connected || playing || paused || (activeRoute()?.points.length || 0) < 2;
  $('pause').disabled = busy || !(playing || paused);
  $('stop').disabled = busy || !connected || !session.playback;
  $('pause').textContent = paused ? 'Resume' : 'Pause';
  for (const id of ['draw', 'new-route', 'clear-route', 'add-node', 'undo-node', 'close-route', 'routes', 'import', 'speed', 'finish']) {
    $(id).disabled = busy || playing || paused;
  }
  $('undo-node').disabled ||= !activeRoute()?.points.length;
  $('close-route').disabled ||= (activeRoute()?.points.length || 0) < 2;
  const closed = Boolean(activeRoute()?.closed);
  $('finish').querySelector('[value="loop"]').disabled = !closed;
  if (!closed && $('finish').value === 'loop') $('finish').value = 'stop';
  for (const node of routeNodes) {
    if (routeEditable()) node.dragging.enable(); else node.dragging.disable();
  }
  $('finish-hint').textContent = {
    stop: 'Stops at the last node. Restore GPS clears simulation.',
    loop: 'Follows the closing segment and repeats until you stop it.',
    restart: 'Jumps from the last node to the first and repeats until stopped.',
    reverse: 'Travels to the end, then reverses along the same nodes. Repeats until stopped.',
  }[$('finish').value];
  $('refresh').disabled = busy;
  $('status').textContent = busy ? 'Working…' : {
    disconnected: 'Disconnected', connecting: 'Connecting…', ready: 'Ready',
    simulating: 'Simulating', playing: 'Playing route', paused: 'Route paused', error: 'Device error',
  }[session.status] || session.status;
  $('status-dot').className = `status-dot ${connected ? 'active' : ''} ${session.error ? 'error' : ''}`;
  $('active-device').textContent = session.device
    ? `${session.device.name} · iOS ${session.device.ios}` : 'Connect a device to begin';
}

function applySession(result) {
  session = result;
  routeArrows?.setDirection(result.playback?.direction === 'reverse');
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
    const { distance_m: distance, total_m: total, speed_kmh: speed, direction, completed_legs: legs, finish } = result.playback;
    $('progress').value = distance / total;
    $('playback-detail').textContent = `${(distance / 1000).toFixed(2)} / ${(total / 1000).toFixed(2)} km · ${speed} km/h${finish !== 'stop' ? ` · ${direction} · ${legs} completed` : ''}`;
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
function routeEditable() { return !busy && !['playing', 'paused'].includes(session.status); }
function routePoints(route) { return route.closed && route.points.length > 1 ? [...route.points, route.points[0]] : route.points; }
function newRoute() {
  routes.push({ name: `Route ${routes.length + 1}`, points: [], closed: false });
  renderRouteOptions();
  return activeRoute();
}
function addNode(point) {
  if (!routeEditable()) return;
  const route = activeRoute() || newRoute();
  if (route.points.length >= 19999) { notice('A route can contain at most 19,999 editable nodes.', true); return; }
  route.points.push([...point]);
  renderRoute();
}

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
    routeNodes.forEach((node) => node.remove());
    routeNodes = [];
    routeLayer = route ? L.polyline(routePoints(route), { color: '#0867b2', weight: 3 }).addTo(map) : null;
    routeArrows.setRoute(route ? routePoints(route) : []);
    routeArrows.layer.bringToFront();
    if (route) {
      const indices = route.points.length <= 200
        ? route.points.map((_, i) => i) : [0, route.points.length - 1];
      for (const index of indices) {
        const node = L.marker(route.points[index], {
          draggable: routeEditable(), title: `Node ${index + 1}`,
          icon: L.divIcon({ className: 'route-node', html: String(index + 1), iconSize: [26, 26], iconAnchor: [13, 13] }),
        }).addTo(map);
        node.on('click', () => {
          if (drawing && index === 0 && route.points.length > 1 && routeEditable()) {
            route.closed = true; finishDrawing();
          } else choosePoint(route.points[index]);
        });
        node.on('dragend', () => {
          if (routeEditable()) {
            const point = node.getLatLng();
            route.points[index] = [point.lat, ((point.lng + 180) % 360 + 360) % 360 - 180];
          }
          renderRoute();
        });
        routeNodes.push(node);
      }
    }
    if (fit && route?.points.length > 1) map.fitBounds(routeLayer.getBounds(), { padding: [40, 40] });
  }
  $('close-route').checked = Boolean(route?.closed);
  $('route-hint').textContent = drawing ? 'Click to connect nodes in order. Click node 1 to close the route, or Finish adding.'
    : route ? `${route.points.length} nodes. ${route.points.length > 200 ? 'Large import: drag endpoints to edit.' : 'Drag numbered nodes to edit. Add nodes extends the route.'}`
      : 'Add nodes on the map or import GPX / GeoJSON.';
  updateControls();
}

function finishDrawing() {
  drawing = false;
  $('draw').textContent = 'Add nodes';
  $('draw').classList.remove('drawing');
  renderRoute();
}

function initializeMap() {
  if (!window.L) {
    notice('Map assets could not load. You can still enter coordinates and simulate a location.', true);
    return;
  }
  map = L.map('map', { zoomControl: false }).setView([37.7749, -122.4194], 12);
  routeArrows = new RouteArrows(map);
  L.control.zoom({ position: 'topright' }).addTo(map);
  const tiles = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19, attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
  }).addTo(map);
  tiles.once('tileerror', () => notice('Map tiles are unavailable. Coordinate entry and device control still work.'));
  map.on('click', ({ latlng }) => {
    const point = [latlng.lat, ((latlng.lng + 180) % 360 + 360) % 360 - 180];
    choosePoint(point);
    if (drawing) addNode(point);
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
  const route = activeRoute() || newRoute();
  route.closed = false;
  drawing = true;
  $('draw').textContent = 'Finish adding';
  $('draw').classList.add('drawing');
  renderRoute();
});
$('new-route').addEventListener('click', () => { finishDrawing(); newRoute(); });
$('add-node').addEventListener('click', () => {
  try { addNode(readPoint()); } catch (error) { notice(error.message, true); }
});
$('undo-node').addEventListener('click', () => {
  const route = activeRoute();
  if (!route) return;
  route.points.pop();
  if (route.points.length < 2) route.closed = false;
  renderRoute();
});
$('close-route').addEventListener('change', () => {
  if (activeRoute()) activeRoute().closed = $('close-route').checked;
  finishDrawing();
});
$('finish').addEventListener('change', updateControls);
$('clear-route').addEventListener('click', () => {
  if (routes.length) routes.splice(Number($('routes').value), 1);
  finishDrawing(); renderRouteOptions();
});
$('routes').addEventListener('change', () => { finishDrawing(); renderRoute(true); });
$('play').addEventListener('click', () => {
  const route = activeRoute();
  if (!route || route.points.length < 2) { notice('Add at least two route points.', true); return; }
  const speed = Number($('speed').value);
  if (!Number.isFinite(speed) || speed <= 0 || speed > 999) {
    notice('Speed must be greater than 0 and no more than 999 km/h.', true); return;
  }
  finishDrawing();
  command('/api/playback', { points: routePoints(route), speed_kmh: speed, finish: $('finish').value }, 'POST', 'Route playing. Pause holds position; Restore GPS stops playback and clears simulation.');
});
$('pause').addEventListener('click', () => {
  const action = session.status === 'paused' ? 'resume' : 'pause';
  command(`/api/playback/${action}`, {}, 'POST', action === 'pause' ? 'Route paused at the last position.' : 'Route resumed.');
});
$('stop').addEventListener('click', () => command('/api/playback/stop', {}, 'POST',
  'Route stopped at the last location. Edit this route or create a new one. Restore GPS returns to your real location.'));

$('import').addEventListener('change', async (event) => {
  const file = event.target.files[0];
  if (!file) return;
  if (file.size > 5 * 1024 * 1024) { notice('Choose a file smaller than 5 MB.', true); return; }
  const form = new FormData(); form.append('file', file);
  try {
    const result = await api('/api/import', { method: 'POST', form });
    finishDrawing();
    for (const route of result.routes) {
      route.closed = route.points.length > 2 && route.points[0].every((n, i) => n === route.points.at(-1)[i]);
      if (route.closed) route.points.pop();
      routes.push(route);
    }
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
      geometry: { type: 'LineString', coordinates: routePoints(r).map(([lat, lon]) => [lon, lat]) } })),
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
