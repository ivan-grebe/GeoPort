// Screen-sized chevrons drawn with Leaflet's existing polyline renderer.
export class RouteArrows {
  constructor(map) {
    this.map = map;
    this.points = [];
    this.reverse = false;
    this.layer = L.polyline([], {
      color: '#0867b2', weight: 3, opacity: 1, interactive: false,
      className: 'route-arrows', smoothFactor: 0,
    }).addTo(map);
    map.on('zoomend moveend resize', () => this.draw());
  }

  setRoute(points) {
    this.points = points;
    this.draw();
  }

  setDirection(reverse) {
    if (this.reverse === reverse) return;
    this.reverse = reverse;
    this.draw();
  }

  draw() {
    const bounds = L.bounds([0, 0], this.map.getSize());
    const points = this.points.map((point) => this.map.latLngToContainerPoint(point));
    const arrows = [];
    let next = 40;
    for (let i = 1; i < points.length && arrows.length < 600; i++) {
      const segment = L.LineUtil.clipSegment(points[i - 1], points[i], bounds);
      if (!segment) { next = 40; continue; }
      const [start, end] = segment;
      const length = start.distanceTo(end);
      if (length === 0) continue;
      const dx = (end.x - start.x) / length, dy = (end.y - start.y) / length;
      const direction = this.reverse ? -1 : 1;
      while (next < length && arrows.length < 600) {
        const x = start.x + dx * next, y = start.y + dy * next;
        arrows.push([
          [x - direction * dx * 5 - dy * 5, y - direction * dy * 5 + dx * 5],
          [x + direction * dx * 5, y + direction * dy * 5],
          [x - direction * dx * 5 + dy * 5, y - direction * dy * 5 - dx * 5],
        ].map((point) => this.map.containerPointToLatLng(point)));
        next += 100;
      }
      next -= length;
    }
    this.layer.setLatLngs(arrows);
  }
}
