"""Normalize supported drawing shapes into a valid GeoJSON polygon."""
import math

def polygon(geometry):
    if not isinstance(geometry, dict):
        raise ValueError('Select a valid area on the map.')
    kind = str(geometry.get('type', '')).lower()
    coords = geometry.get('coordinates')
    if not isinstance(coords, list) or not coords:
        raise ValueError('Area coordinates are missing.')
    if kind == 'rectangle':
        if len(coords) != 2:
            raise ValueError('Rectangle needs two corners.')
        a, b = coords
        coords = [[a[0],a[1]], [b[0],a[1]], [b[0],b[1]], [a[0],b[1]], [a[0],a[1]]]
    elif kind == 'polygon':
        if isinstance(coords[0][0], list):
            coords = coords[0]
    else:
        raise ValueError('Use a rectangle or polygon.')
    for point in coords:
        if len(point) != 2 or not all(isinstance(x, (int,float)) and math.isfinite(x) for x in point):
            raise ValueError('Invalid coordinates.')
        if not -180 <= point[0] <= 180 or not -90 <= point[1] <= 90:
            raise ValueError('Coordinates are outside the globe.')
    if coords[-1] != coords[0]:
        coords = coords + [coords[0]]
    if len(set(map(tuple, coords))) < 3:
        raise ValueError('Area needs at least three distinct corners.')
    area = abs(sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(coords,coords[1:]))) / 2
    if area <= 1e-10:
        raise ValueError('Selected area has zero size.')
    return {'type': 'Polygon', 'coordinates': [coords]}

def centroid(geometry):
    ring = polygon(geometry)['coordinates'][0][:-1]
    return {'lat': sum(p[1] for p in ring)/len(ring), 'lon': sum(p[0] for p in ring)/len(ring)}
