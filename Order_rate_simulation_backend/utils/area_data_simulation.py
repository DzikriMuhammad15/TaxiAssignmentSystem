import random
import threading
import time
import logging
from functools import lru_cache
from utils.graph import G, get_node_lat_lon, get_route, get_nearest_node, find_edges, get_route_by_lat_lon 
from geopy.distance import geodesic


logger = logging.getLogger(__name__)

AREA_DATA_INPUT = [
    {"latitude": -6.8904, "longitude": 107.6102, "order_rate": 5, 
        "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},
    {"latitude": -6.92156, "longitude": 107.60766,
        "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50, "order_rate": 7},
    {"latitude": -6.91417, "longitude": 107.60250,
        "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50, "order_rate": 12},
    {"latitude": -6.921027, "longitude": 107.610027,
        "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50, "order_rate": 9},
    {"latitude": -6.900306, "longitude": 107.618709,
        "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50, "order_rate": 5},
    {"latitude": -6.91333, "longitude": 107.60778,
        "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50, "order_rate": 6},
    {"latitude": -6.829484, "longitude": 107.596632,
        "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50, "order_rate": 8},
    {"latitude": -6.8782, "longitude": 107.5930,
        "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50, "order_rate": 12},
    {"latitude": -6.8967, "longitude": 107.6011,
        "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50, "order_rate": 6},
    {"latitude": -6.9168, "longitude": 107.6215,
        "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50, "order_rate": 7}
]

AREA_DATA = {}
_update_lock = threading.Lock()
_thread_running = True


logger.info("Initializing area data...")
for i, area_input in enumerate(AREA_DATA_INPUT):
    try:
        lat = area_input.get("latitude")
        lon = area_input.get("longitude")
        area_node_id = get_nearest_node(lat=lat, lon=lon, G=G)
        node_lat, node_lon = get_node_lat_lon(node_id=area_node_id, G=G)
        
        AREA_DATA[area_node_id] = {
            "area_lat": node_lat, 
            "area_lon": node_lon, 
            "mean_order_rate": area_input.get("mean_order_rate"),
            "std_order_rate": area_input.get("std_order_rate"),
            "min_order_rate": area_input.get("min_order_rate"),
            "max_order_rate": area_input.get("max_order_rate"),
            "area_order_rate": area_input.get("order_rate")
        }
        
    except Exception as e:
        logger.error(f"Error initializing area {i}: {str(e)}")

logger.info(f"Initialized {len(AREA_DATA)} area data entries")

def random_area_order_rate():
    
    logger.info("Starting area order rate update thread")
    
    while _thread_running:
        try:
            with _update_lock:
                for area_node_id, data in AREA_DATA.items():
                    min_range = data["min_order_rate"]
                    max_range = data["max_order_rate"]
                    mean = data["mean_order_rate"]
                    std = data["std_order_rate"]
                    
                    new_order_rate = max(min_range, min(int(round(random.gauss(mean, std))), max_range))
                    data["area_order_rate"] = new_order_rate
                    
            logger.debug(f"Updated {len(AREA_DATA)} area order rates")
            
        except Exception as e:
            logger.error(f"Error updating area order rates: {str(e)}")
            

        time.sleep(180)
    
    logger.info("Area order rate update thread stopped")


update_thread = threading.Thread(target=random_area_order_rate, daemon=True, name="area_order_rate_updater")
update_thread.start()

@lru_cache(maxsize=1024)
def get_cached_node_order_rate(node_id):
    
    with _update_lock:
        if node_id in AREA_DATA:
            return node_id, AREA_DATA[node_id]["area_order_rate"]
    return None, 0

def get_node_order_rate(node_id, area_data=None):
    
    return get_cached_node_order_rate(node_id)

def get_cumulative_order_rate(coordAwal, coordAkhir, G=G):
    
    try:
        logger.debug(f"Calculating route from {coordAwal} to {coordAkhir}")
        route = get_route_by_lat_lon(coordAwal=coordAwal, coordAkhir=coordAkhir, G=G)
        print(f"route: {route}")
        if not route:
            logger.warning("No route found")
            return 0
            
        cumulative_order_rate = 0
        visited_areas = set()
        
        for node in route:

            if node in AREA_DATA and node not in visited_areas:
                cumulative_order_rate += AREA_DATA[node]["area_order_rate"]
                visited_areas.add(node)
        
        logger.debug(f"Cumulative order rate: {cumulative_order_rate}")
        return cumulative_order_rate
        
    except Exception as e:
        logger.error(f"Error calculating cumulative order rate: {str(e)}")
        return 0

def stop_background_thread():
    
    global _thread_running
    _thread_running = False
