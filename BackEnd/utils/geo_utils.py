import math
import polyline
from geopy.distance import geodesic
import logging

logger = logging.getLogger(__name__)

def jarak_radius(coordAwal, coordAkhir):
    try:
        return geodesic(coordAwal, coordAkhir).meters
    except Exception as e:
        return float('inf')

def getNearestBase(coord_taxi, bases):
    try:
        nearest_base = None
        min_distance = float('inf')

        for base_id, loc in bases.items():
            if "latitude" not in loc or "longitude" not in loc:
                continue
                
            base_coord = (loc["latitude"], loc["longitude"])
            try:
                dist = geodesic(coord_taxi, base_coord).meters
                if dist < min_distance:
                    min_distance = dist
                    nearest_base = base_id
            except Exception as e:
                pass

        return nearest_base
    except Exception as e:
        return None

def _dist_point_to_segment(p, a, b):
    try:
        lat0, lon0 = p
        def to_xy(lat, lon):
            x = (lon - lon0) * math.cos(math.radians(lat0)) * 111320
            y = (lat - lat0) * 110540
            return x, y

        px, py = to_xy(*p)
        ax, ay = to_xy(*a)
        bx, by = to_xy(*b)
        dx, dy = bx - ax, by - ay
        
        if dx == 0 and dy == 0:
            return geodesic(p, a).meters
            
        t = ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)
        t = max(0, min(1, t))
        proj_lat = a[0] + t * (b[0] - a[0])
        proj_lon = a[1] + t * (b[1] - a[1])
        return geodesic(p, (proj_lat, proj_lon)).meters
    except Exception as e:
        return float('inf')

def is_melenceng(taxi_id, route, radius, taxi_current_state):
    try:
        state = taxi_current_state.get(str(taxi_id))
        if not state:
            return False
            
        p = (state['latitude'], state['longitude'])
            
        min_dist = float('inf')
        for i in range(len(route) - 1):
            a = route[i]
            b = route[i + 1]
            d = _dist_point_to_segment(p, a, b)
            if d < min_dist:
                min_dist = d
                
        is_deviated = min_dist > radius
        return is_deviated
    except Exception as e:
        return False
