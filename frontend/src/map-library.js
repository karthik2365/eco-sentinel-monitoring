import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import 'leaflet-draw';
import 'leaflet-draw/dist/leaflet.draw.css';
// Leaflet.draw 1.0.4 assigns an undeclared `type` in readableArea under strict modules.
L.GeometryUtil.readableArea = (area, metric = true) => {
  if (!metric) return `${(area / 4046.8564224).toFixed(2)} acres`;
  return area >= 1000000 ? `${(area / 1000000).toFixed(2)} km²` : `${(area / 10000).toFixed(2)} ha`;
};
export default L;
