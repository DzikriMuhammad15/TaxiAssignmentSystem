import random
import time
import threading
import logging
from functools import lru_cache
from .graph import get_nearest_node, G
import numpy as np


logger = logging.getLogger(__name__)

base_current_state = [
    {"name": "Gedung Sate #1", "latitude": -6.9024, "longitude": 107.6191, "capacity": 4, "order_rate": 16, "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},
    {"name": "Braga Street #1", "latitude": -6.9237, "longitude": 107.6056, "capacity": 5, "order_rate": 11, "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},
    {"name": "Paris Van Java #1", "latitude": -6.8904, "longitude": 107.5949, "capacity": 3, "order_rate": 8, "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},
    {"name": "Trans Studio Bandung #1", "latitude": -6.9242, "longitude": 107.6359, "capacity": 3, "order_rate": 13, "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},
    {"name": "Rumah Mode #1", "latitude": -6.8912, "longitude": 107.6081, "capacity": 2, "order_rate": 17, "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},
    {"name": "Tangkuban Perahu #1", "latitude": -6.7634, "longitude": 107.6098, "capacity": 3, "order_rate": 7, "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},
    {"name": "Kawah Putih #1", "latitude": -7.1003, "longitude": 107.2444, "capacity": 5, "order_rate": 9, "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},
    {"name": "Djuanda Park #1", "latitude": -6.8640, "longitude": 107.6195, "capacity": 4, "order_rate": 10, "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},
    {"name": "Tebing Keraton #1", "latitude": -6.8780, "longitude": 107.6218, "capacity": 2, "order_rate": 6, "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},
    {"name": "Curug Omas #1", "latitude": -6.8813, "longitude": 107.6202, "capacity": 4, "order_rate": 14, "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},
    {"name": "Alun-Alun Bandung #1", "latitude": -6.9217, "longitude": 107.6077, "capacity": 4, "order_rate": 18, "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},
    {"name": "Stasiun Bandung #1", "latitude": -6.9175, "longitude": 107.6030, "capacity": 3, "order_rate": 15, "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},
    {"name": "Pasar Baru #1", "latitude": -6.9208, "longitude": 107.6021, "capacity": 2, "order_rate": 12, "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},
    {"name": "Cihampelas Walk #1", "latitude": -6.8938, "longitude": 107.6052, "capacity": 3, "order_rate": 11, "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},
    {"name": "Paskal Hyper Square #1", "latitude": -6.9131, "longitude": 107.5939, "capacity": 3, "order_rate": 12, "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},
    {"name": "Universitas Padjadjaran #1", "latitude": -6.9247, "longitude": 107.7726, "capacity": 5, "order_rate": 7, "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},
    {"name": "ITB Ganesa #1", "latitude": -6.8906, "longitude": 107.6107, "capacity": 4, "order_rate": 9, "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},
    {"name": "BIP #1", "latitude": -6.9112, "longitude": 107.6097, "capacity": 4, "order_rate": 13, "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},
    {"name": "PVJ #1", "latitude": -6.8898, "longitude": 107.5954, "capacity": 3, "order_rate": 17, "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},
    {"name": "Museum Geologi #1", "latitude": -6.9026, "longitude": 107.6203, "capacity": 3, "order_rate": 6, "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},
    {"name": "Kebun Binatang Bandung #1", "latitude": -6.8895, "longitude": 107.6071, "capacity": 5, "order_rate": 14, "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},
    {"name": "Dago Dreampark #1", "latitude": -6.8571, "longitude": 107.6224, "capacity": 3, "order_rate": 13, "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},
    {"name": "Saung Angklung Udjo #1", "latitude": -6.9004, "longitude": 107.6618, "capacity": 4, "order_rate": 15, "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},
    {"name": "Gasibu #1", "latitude": -6.9000, "longitude": 107.6174, "capacity": 2, "order_rate": 7, "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},
    {"name": "Cicaheum Terminal #1", "latitude": -6.9032, "longitude": 107.6779, "capacity": 4, "order_rate": 12, "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},
    {"name": "Leuwipanjang Terminal #1", "latitude": -6.9333, "longitude": 107.5742, "capacity": 3, "order_rate": 10, "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},
    {"name": "Stasiun Kiaracondong #1", "latitude": -6.9250, "longitude": 107.6613, "capacity": 3, "order_rate": 11, "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},
    {"name": "Pasar Kosambi #1", "latitude": -6.9182, "longitude": 107.6212, "capacity": 2, "order_rate": 5, "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},
    {"name": "Pasar Baru Trade Center #1", "latitude": -6.9190, "longitude": 107.6023, "capacity": 4, "order_rate": 16, "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},
    {"name": "Balai Kota Bandung #1", "latitude": -6.9174, "longitude": 107.6109, "capacity": 3, "order_rate": 13, "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},
    {"name": "Taman Vanda #1", "latitude": -6.9177, "longitude": 107.6101, "capacity": 3, "order_rate": 7, "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},
    {"name": "Cihampelas Skywalk #1", "latitude": -6.8939, "longitude": 107.6043, "capacity": 2, "order_rate": 9, "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},
    {"name": "Teras Cihampelas #1", "latitude": -6.8932, "longitude": 107.6049, "capacity": 4, "order_rate": 6, "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},
    {"name": "Cimahi Mall #1", "latitude": -6.8723, "longitude": 107.5415, "capacity": 4, "order_rate": 8, "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},
    {"name": "BTC Fashion Mall #1", "latitude": -6.8860, "longitude": 107.5802, "capacity": 3, "order_rate": 9, "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},
    {"name": "Pasar Andir #1", "latitude": -6.9179, "longitude": 107.5901, "capacity": 3, "order_rate": 10, "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},
    {"name": "Masjid Raya Bandung #1", "latitude": -6.9219, "longitude": 107.6064, "capacity": 4, "order_rate": 15, "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},
    {"name": "Museum Konferensi Asia Afrika #1", "latitude": -6.9213, "longitude": 107.6095, "capacity": 2, "order_rate": 7, "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},
    {"name": "Alun-Alun Ujungberung #1", "latitude": -6.9031, "longitude": 107.7083, "capacity": 3, "order_rate": 8, "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},
    {"name": "Summarecon Mall Bandung #1", "latitude": -6.9600, "longitude": 107.7170, "capacity": 5, "order_rate": 13, "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},
     {"name": "Lembang Park and Zoo #1", "latitude": -6.8253, "longitude": 107.6118, "capacity": 2, "order_rate": 6, "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},
    {"name": "The Lodge Maribaya #1", "latitude": -6.8019, "longitude": 107.6861, "capacity": 2, "order_rate": 5, "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},
    {"name": "Dusun Bambu #1", "latitude": -6.7913, "longitude": 107.5947, "capacity": 2, "order_rate": 7, "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},
    {"name": "Floating Market Lembang #1", "latitude": -6.8123, "longitude": 107.6164, "capacity": 3, "order_rate": 9, "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},
    {"name": "Amazing Art World #1", "latitude": -6.8577, "longitude": 107.5890, "capacity": 2, "order_rate": 10, "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},
    {"name": "Taman Lansia #1", "latitude": -6.9020, "longitude": 107.6221, "capacity": 2, "order_rate": 6, "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},
    {"name": "Taman Super Hero #1", "latitude": -6.9111, "longitude": 107.6332, "capacity": 3, "order_rate": 8, "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},
    {"name": "Peta Park #1", "latitude": -6.9561, "longitude": 107.6283, "capacity": 3, "order_rate": 5, "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},
    {"name": "Museum Sri Baduga #1", "latitude": -6.9334, "longitude": 107.6023, "capacity": 3, "order_rate": 7, "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},
    {"name": "Kampung Korea Bandung #1", "latitude": -6.9022, "longitude": 107.6278, "capacity": 2, "order_rate": 11, "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},
    {"name": "Kota Baru Parahyangan #1", "latitude": -6.8655, "longitude": 107.4750, "capacity": 3, "order_rate": 7, "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},
    {"name": "Masjid Al-Irsyad #1", "latitude": -6.8697, "longitude": 107.4813, "capacity": 2, "order_rate": 6, "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},
    {"name": "Masjid Raya Al-Jabbar #1", "latitude": -6.9450, "longitude": 107.7261, "capacity": 4, "order_rate": 14, "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},
    {"name": "GOR Saparua #1", "latitude": -6.9051, "longitude": 107.6212, "capacity": 3, "order_rate": 8, "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},
    {"name": "GOR Pajajaran #1", "latitude": -6.9055, "longitude": 107.5992, "capacity": 3, "order_rate": 9, "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},
    {"name": "GOR C-Tra Arena #1", "latitude": -6.9137, "longitude": 107.6393, "capacity": 2, "order_rate": 10, "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},
    {"name": "Orchid Forest Cikole #1", "latitude": -6.7771, "longitude": 107.6316, "capacity": 2, "order_rate": 6, "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},
    {"name": "Stasiun Padalarang Whoosh #1", "latitude": -6.8375, "longitude": 107.4708, "capacity": 2, "order_rate": 6, "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},
    {"name": "Stasiun Tegalluar Whoosh #1", "latitude": -6.9850, "longitude": 107.7400, "capacity": 2, "order_rate": 7, "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},
    {"name": "Rest Area Alun-Alun Lembang #1", "latitude": -6.8180, "longitude": 107.6169, "capacity": 2, "order_rate": 4, "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},
    {"name": "Komplek Pemkab Bandung (Soreang) #1", "latitude": -7.0223, "longitude": 107.5186, "capacity": 3, "order_rate": 8, "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50}
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
