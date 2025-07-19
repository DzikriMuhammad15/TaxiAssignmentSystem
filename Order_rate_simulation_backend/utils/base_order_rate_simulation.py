import random
import time
import threading
import logging
from functools import lru_cache
from .graph import get_nearest_node, G
import numpy as np


logger = logging.getLogger(__name__)

base_current_state = [
    # MALL
    {"name": "d'Botanica Pasteur", "latitude": -6.8812, "longitude": 107.5800, "capacity": 3, "order_rate": 12,  "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},
    {"name": "Cihampelas Walk (Ciwalk)", "latitude": -6.8938, "longitude": 107.6052, "capacity": 4, "order_rate": 11,  "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},
    {"name": "Paris Van Java (PVJ)", "latitude": -6.8895, "longitude": 107.5957, "capacity": 4, "order_rate": 15,  "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},
    {"name": "Bandung Indah Plaza (BIP)", "latitude": -6.9112, "longitude": 107.6097, "capacity": 3, "order_rate": 14,  "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},
    {"name": "Summarecon Mall Bandung", "latitude": -6.9600, "longitude": 107.7170, "capacity": 5, "order_rate": 13,  "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},
    {"name": "Trans Studio Mall Bandung", "latitude": -6.9276, "longitude": 107.6364, "capacity": 5, "order_rate": 20,  "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},

    # MODA TRANSPORTASI
    {"name": "Stasiun Bandung", "latitude": -6.9175, "longitude": 107.6030, "capacity": 4, "order_rate": 18,  "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},
    {"name": "Stasiun Padalarang Whoosh", "latitude": -6.8375, "longitude": 107.4708, "capacity": 2, "order_rate": 6,  "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},
    {"name": "Stasiun Tegalluar Whoosh", "latitude": -6.9850, "longitude": 107.7400, "capacity": 2, "order_rate": 7,  "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},
    {"name": "Terminal Leuwipanjang", "latitude": -6.9333, "longitude": 107.5742, "capacity": 3, "order_rate": 10,  "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},
    {"name": "Kertajati Internasional Airport", "latitude": -6.5569, "longitude": 108.2314, "capacity": 6, "order_rate": 5,  "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},
    {"name": "Cititrans Dipatiukur", "latitude": -6.8840, "longitude": 107.6186, "capacity": 2, "order_rate": 9,  "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},
    {"name": "Shuttle Drop Off Pasteur", "latitude": -6.8855, "longitude": 107.5779, "capacity": 3, "order_rate": 8,  "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},

    # RESIDENSIAL
    {"name": "Majesty Apartement", "latitude": -6.8858, "longitude": 107.5790, "capacity": 2, "order_rate": 6,  "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},
    {"name": "Kota Baru Parahyangan", "latitude": -6.8655, "longitude": 107.4750, "capacity": 3, "order_rate": 7,  "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},

    # TEMPAT HIBURAN MALAM
    {"name": "W Super Club", "latitude": -6.9180, "longitude": 107.6150, "capacity": 2, "order_rate": 9,  "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},
    {"name": "MOD Pool and Club", "latitude": -6.9205, "longitude": 107.6162, "capacity": 2, "order_rate": 10,  "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},

    # LEASURE PARK
    {"name": "Dusun Bambu", "latitude": -6.7904, "longitude": 107.5950, "capacity": 2, "order_rate": 7,  "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},
    {"name": "Lembang Park Zoo", "latitude": -6.8247, "longitude": 107.6133, "capacity": 2, "order_rate": 6,  "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},
    {"name": "The Lodge Maribaya", "latitude": -6.8012, "longitude": 107.6857, "capacity": 2, "order_rate": 5,  "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},

    # GOVERNMENT
    {"name": "Komplek Pemerintahan Kab. Bandung (Soreang)", "latitude": -7.0223, "longitude": 107.5186, "capacity": 3, "order_rate": 8,  "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},

    # OTHERS
    {"name": "Rest Area Alun-Alun Lembang", "latitude": -6.8180, "longitude": 107.6169, "capacity": 2, "order_rate": 4,  "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50}
]


@lru_cache(maxsize=128)
def get_cached_nearest_node(lat, lon):
    
    return str(get_nearest_node(lat, lon, G=G))


for base in base_current_state:
    base["id"] = get_cached_nearest_node(base.get("latitude"), base.get("longitude"))


base_order_rate = {}
for base in base_current_state:
    base_id = base.get("id")
    min_range = base.get("min_order_rate")
    max_range = base.get("max_order_rate")
    mean = base.get("mean_order_rate")
    std = base.get("std_order_rate")
    sampled_rate = np.random.poisson(lam=mean)
    new_order_rate = max(min_range, min(sampled_rate, max_range))
    base_order_rate[base_id] = new_order_rate


_thread_running = True
_update_lock = threading.Lock()

def random_base_order_rate():
    
    logger.info("Starting base order rate update thread")
    
    while _thread_running:
        try:
            with _update_lock:
                for base in base_current_state:
                    base_id = base.get("id")
                    min_range = base.get("min_order_rate")
                    max_range = base.get("max_order_rate")
                    mean = base.get("mean_order_rate")
                    std = base.get("std_order_rate")
                    

                    sampled_rate = np.random.poisson(lam=mean)
                    new_order_rate = max(min_range, min(sampled_rate, max_range))
                    base_order_rate[base_id] = new_order_rate
                    
            logger.debug(f"Updated {len(base_current_state)} base order rates")
            
        except Exception as e:
            logger.error(f"Error updating base order rates: {str(e)}")
            

        time.sleep(120)
    
    logger.info("Base order rate update thread stopped")


update_thread = threading.Thread(target=random_base_order_rate, daemon=True, name="base_order_rate_updater")
update_thread.start()

def get_base_order_rate(base_id):
    
    with _update_lock:
        return base_order_rate.get(base_id)

def stop_background_thread():
    
    global _thread_running
    _thread_running = False
