import random
import threading
import time
import logging
from functools import lru_cache
from utils.graph import G, get_node_lat_lon, get_route, get_nearest_node, find_edges, get_route_by_lat_lon 
from geopy.distance import geodesic
import numpy as np


logger = logging.getLogger(__name__)



AREA_USE = "area_data_input_100_area"

AREA_DATA_INPUT_100_AREA = [
    {"latitude": -6.9175, "longitude": 107.6030, "order_rate": 15, "mean_order_rate": 12, "std_order_rate": 2, "min_order_rate": 5, "max_order_rate": 25},
    {"latitude": -6.9200, "longitude": 107.6050, "order_rate": 12, "mean_order_rate": 10, "std_order_rate": 2, "min_order_rate": 3, "max_order_rate": 20},
    {"latitude": -6.9150, "longitude": 107.6080, "order_rate": 18, "mean_order_rate": 15, "std_order_rate": 3, "min_order_rate": 8, "max_order_rate": 30},
    {"latitude": -6.9180, "longitude": 107.6100, "order_rate": 14, "mean_order_rate": 11, "std_order_rate": 2, "min_order_rate": 4, "max_order_rate": 22},
    {"latitude": -6.9220, "longitude": 107.6020, "order_rate": 16, "mean_order_rate": 13, "std_order_rate": 2, "min_order_rate": 6, "max_order_rate": 25},
    

    {"latitude": -6.8500, "longitude": 107.6000, "order_rate": 8, "mean_order_rate": 7, "std_order_rate": 1, "min_order_rate": 2, "max_order_rate": 15},
    {"latitude": -6.8400, "longitude": 107.5950, "order_rate": 6, "mean_order_rate": 5, "std_order_rate": 1, "min_order_rate": 1, "max_order_rate": 12},
    {"latitude": -6.8300, "longitude": 107.6100, "order_rate": 7, "mean_order_rate": 6, "std_order_rate": 1, "min_order_rate": 2, "max_order_rate": 14},
    {"latitude": -6.8200, "longitude": 107.6150, "order_rate": 9, "mean_order_rate": 8, "std_order_rate": 1, "min_order_rate": 3, "max_order_rate": 16},
    {"latitude": -6.8100, "longitude": 107.6200, "order_rate": 5, "mean_order_rate": 4, "std_order_rate": 1, "min_order_rate": 1, "max_order_rate": 10},
    

    {"latitude": -6.9500, "longitude": 107.6000, "order_rate": 11, "mean_order_rate": 9, "std_order_rate": 2, "min_order_rate": 3, "max_order_rate": 18},
    {"latitude": -6.9600, "longitude": 107.6100, "order_rate": 13, "mean_order_rate": 11, "std_order_rate": 2, "min_order_rate": 4, "max_order_rate": 20},
    {"latitude": -6.9700, "longitude": 107.6200, "order_rate": 10, "mean_order_rate": 8, "std_order_rate": 2, "min_order_rate": 2, "max_order_rate": 16},
    {"latitude": -6.9800, "longitude": 107.6300, "order_rate": 12, "mean_order_rate": 10, "std_order_rate": 2, "min_order_rate": 3, "max_order_rate": 19},
    {"latitude": -6.9900, "longitude": 107.6400, "order_rate": 9, "mean_order_rate": 7, "std_order_rate": 1, "min_order_rate": 2, "max_order_rate": 15},
    

    {"latitude": -6.9000, "longitude": 107.6500, "order_rate": 14, "mean_order_rate": 12, "std_order_rate": 2, "min_order_rate": 5, "max_order_rate": 22},
    {"latitude": -6.9100, "longitude": 107.6600, "order_rate": 16, "mean_order_rate": 14, "std_order_rate": 3, "min_order_rate": 6, "max_order_rate": 25},
    {"latitude": -6.9200, "longitude": 107.6700, "order_rate": 11, "mean_order_rate": 9, "std_order_rate": 2, "min_order_rate": 3, "max_order_rate": 18},
    {"latitude": -6.9300, "longitude": 107.6800, "order_rate": 13, "mean_order_rate": 11, "std_order_rate": 2, "min_order_rate": 4, "max_order_rate": 20},
    {"latitude": -6.9400, "longitude": 107.6900, "order_rate": 8, "mean_order_rate": 6, "std_order_rate": 1, "min_order_rate": 2, "max_order_rate": 14},
    

    {"latitude": -6.9000, "longitude": 107.5500, "order_rate": 10, "mean_order_rate": 8, "std_order_rate": 2, "min_order_rate": 2, "max_order_rate": 16},
    {"latitude": -6.9100, "longitude": 107.5400, "order_rate": 7, "mean_order_rate": 6, "std_order_rate": 1, "min_order_rate": 1, "max_order_rate": 13},
    {"latitude": -6.9200, "longitude": 107.5300, "order_rate": 9, "mean_order_rate": 7, "std_order_rate": 1, "min_order_rate": 2, "max_order_rate": 15},
    {"latitude": -6.9300, "longitude": 107.5200, "order_rate": 6, "mean_order_rate": 5, "std_order_rate": 1, "min_order_rate": 1, "max_order_rate": 11},
    {"latitude": -6.9400, "longitude": 107.5100, "order_rate": 8, "mean_order_rate": 6, "std_order_rate": 1, "min_order_rate": 2, "max_order_rate": 14},
    

    {"latitude": -6.8800, "longitude": 107.5800, "order_rate": 12, "mean_order_rate": 10, "std_order_rate": 2, "min_order_rate": 3, "max_order_rate": 19},
    {"latitude": -6.8900, "longitude": 107.5900, "order_rate": 15, "mean_order_rate": 13, "std_order_rate": 2, "min_order_rate": 5, "max_order_rate": 23},
    {"latitude": -6.9000, "longitude": 107.6000, "order_rate": 17, "mean_order_rate": 15, "std_order_rate": 3, "min_order_rate": 7, "max_order_rate": 26},
    {"latitude": -6.8700, "longitude": 107.6200, "order_rate": 11, "mean_order_rate": 9, "std_order_rate": 2, "min_order_rate": 3, "max_order_rate": 18},
    {"latitude": -6.8600, "longitude": 107.6300, "order_rate": 9, "mean_order_rate": 7, "std_order_rate": 1, "min_order_rate": 2, "max_order_rate": 15},
    

    {"latitude": -6.8500, "longitude": 107.6400, "order_rate": 13, "mean_order_rate": 11, "std_order_rate": 2, "min_order_rate": 4, "max_order_rate": 20},
    {"latitude": -6.8400, "longitude": 107.6500, "order_rate": 10, "mean_order_rate": 8, "std_order_rate": 2, "min_order_rate": 2, "max_order_rate": 16},
    {"latitude": -6.8300, "longitude": 107.6600, "order_rate": 8, "mean_order_rate": 6, "std_order_rate": 1, "min_order_rate": 2, "max_order_rate": 14},
    {"latitude": -6.8200, "longitude": 107.6700, "order_rate": 7, "mean_order_rate": 5, "std_order_rate": 1, "min_order_rate": 1, "max_order_rate": 12},
    {"latitude": -6.8100, "longitude": 107.6800, "order_rate": 6, "mean_order_rate": 4, "std_order_rate": 1, "min_order_rate": 1, "max_order_rate": 10},
    

    {"latitude": -6.9500, "longitude": 107.5500, "order_rate": 11, "mean_order_rate": 9, "std_order_rate": 2, "min_order_rate": 3, "max_order_rate": 18},
    {"latitude": -6.9600, "longitude": 107.5600, "order_rate": 14, "mean_order_rate": 12, "std_order_rate": 2, "min_order_rate": 5, "max_order_rate": 22},
    {"latitude": -6.9700, "longitude": 107.5700, "order_rate": 12, "mean_order_rate": 10, "std_order_rate": 2, "min_order_rate": 3, "max_order_rate": 19},
    {"latitude": -6.9800, "longitude": 107.5800, "order_rate": 9, "mean_order_rate": 7, "std_order_rate": 1, "min_order_rate": 2, "max_order_rate": 15},
    {"latitude": -6.9900, "longitude": 107.5900, "order_rate": 10, "mean_order_rate": 8, "std_order_rate": 2, "min_order_rate": 2, "max_order_rate": 16},
    

    {"latitude": -6.8750, "longitude": 107.5750, "order_rate": 13, "mean_order_rate": 11, "std_order_rate": 2, "min_order_rate": 4, "max_order_rate": 20},
    {"latitude": -6.8850, "longitude": 107.5850, "order_rate": 15, "mean_order_rate": 13, "std_order_rate": 2, "min_order_rate": 5, "max_order_rate": 23},
    {"latitude": -6.8950, "longitude": 107.5950, "order_rate": 16, "mean_order_rate": 14, "std_order_rate": 3, "min_order_rate": 6, "max_order_rate": 25},
    {"latitude": -6.9050, "longitude": 107.6050, "order_rate": 18, "mean_order_rate": 16, "std_order_rate": 3, "min_order_rate": 8, "max_order_rate": 28},
    {"latitude": -6.9150, "longitude": 107.6150, "order_rate": 14, "mean_order_rate": 12, "std_order_rate": 2, "min_order_rate": 5, "max_order_rate": 22},
    

    {"latitude": -6.8650, "longitude": 107.5650, "order_rate": 11, "mean_order_rate": 9, "std_order_rate": 2, "min_order_rate": 3, "max_order_rate": 18},
    {"latitude": -6.8550, "longitude": 107.5550, "order_rate": 8, "mean_order_rate": 6, "std_order_rate": 1, "min_order_rate": 2, "max_order_rate": 14},
    {"latitude": -6.8450, "longitude": 107.5450, "order_rate": 7, "mean_order_rate": 5, "std_order_rate": 1, "min_order_rate": 1, "max_order_rate": 12},
    {"latitude": -6.8350, "longitude": 107.5350, "order_rate": 6, "mean_order_rate": 4, "std_order_rate": 1, "min_order_rate": 1, "max_order_rate": 10},
    {"latitude": -6.8250, "longitude": 107.5250, "order_rate": 5, "mean_order_rate": 3, "std_order_rate": 1, "min_order_rate": 1, "max_order_rate": 8},
    

    {"latitude": -6.9250, "longitude": 107.6250, "order_rate": 12, "mean_order_rate": 10, "std_order_rate": 2, "min_order_rate": 3, "max_order_rate": 19},
    {"latitude": -6.9350, "longitude": 107.6350, "order_rate": 10, "mean_order_rate": 8, "std_order_rate": 2, "min_order_rate": 2, "max_order_rate": 16},
    {"latitude": -6.9450, "longitude": 107.6450, "order_rate": 9, "mean_order_rate": 7, "std_order_rate": 1, "min_order_rate": 2, "max_order_rate": 15},
    {"latitude": -6.9550, "longitude": 107.6550, "order_rate": 11, "mean_order_rate": 9, "std_order_rate": 2, "min_order_rate": 3, "max_order_rate": 18},
    {"latitude": -6.9650, "longitude": 107.6650, "order_rate": 8, "mean_order_rate": 6, "std_order_rate": 1, "min_order_rate": 2, "max_order_rate": 14},
    

    {"latitude": -6.8775, "longitude": 107.5775, "order_rate": 13, "mean_order_rate": 11, "std_order_rate": 2, "min_order_rate": 4, "max_order_rate": 20},
    {"latitude": -6.8875, "longitude": 107.5875, "order_rate": 14, "mean_order_rate": 12, "std_order_rate": 2, "min_order_rate": 5, "max_order_rate": 22},
    {"latitude": -6.8975, "longitude": 107.5975, "order_rate": 15, "mean_order_rate": 13, "std_order_rate": 2, "min_order_rate": 5, "max_order_rate": 23},
    {"latitude": -6.9075, "longitude": 107.6075, "order_rate": 17, "mean_order_rate": 15, "std_order_rate": 3, "min_order_rate": 7, "max_order_rate": 26},
    {"latitude": -6.9175, "longitude": 107.6175, "order_rate": 16, "mean_order_rate": 14, "std_order_rate": 3, "min_order_rate": 6, "max_order_rate": 25},
    

    {"latitude": -6.8625, "longitude": 107.5625, "order_rate": 10, "mean_order_rate": 8, "std_order_rate": 2, "min_order_rate": 2, "max_order_rate": 16},
    {"latitude": -6.8525, "longitude": 107.5525, "order_rate": 7, "mean_order_rate": 5, "std_order_rate": 1, "min_order_rate": 1, "max_order_rate": 12},
    {"latitude": -6.8425, "longitude": 107.5425, "order_rate": 6, "mean_order_rate": 4, "std_order_rate": 1, "min_order_rate": 1, "max_order_rate": 10},
    {"latitude": -6.8325, "longitude": 107.5325, "order_rate": 5, "mean_order_rate": 3, "std_order_rate": 1, "min_order_rate": 1, "max_order_rate": 8},
    {"latitude": -6.8225, "longitude": 107.5225, "order_rate": 4, "mean_order_rate": 2, "std_order_rate": 1, "min_order_rate": 1, "max_order_rate": 6},
    

    {"latitude": -6.9275, "longitude": 107.6275, "order_rate": 11, "mean_order_rate": 9, "std_order_rate": 2, "min_order_rate": 3, "max_order_rate": 18},
    {"latitude": -6.9375, "longitude": 107.6375, "order_rate": 9, "mean_order_rate": 7, "std_order_rate": 1, "min_order_rate": 2, "max_order_rate": 15},
    {"latitude": -6.9475, "longitude": 107.6475, "order_rate": 8, "mean_order_rate": 6, "std_order_rate": 1, "min_order_rate": 2, "max_order_rate": 14},
    {"latitude": -6.9575, "longitude": 107.6575, "order_rate": 10, "mean_order_rate": 8, "std_order_rate": 2, "min_order_rate": 2, "max_order_rate": 16},
    {"latitude": -6.9675, "longitude": 107.6675, "order_rate": 7, "mean_order_rate": 5, "std_order_rate": 1, "min_order_rate": 1, "max_order_rate": 12},
    

    {"latitude": -6.8700, "longitude": 107.5700, "order_rate": 12, "mean_order_rate": 10, "std_order_rate": 2, "min_order_rate": 3, "max_order_rate": 19},
    {"latitude": -6.8800, "longitude": 107.5800, "order_rate": 13, "mean_order_rate": 11, "std_order_rate": 2, "min_order_rate": 4, "max_order_rate": 20},
    {"latitude": -6.8900, "longitude": 107.5900, "order_rate": 14, "mean_order_rate": 12, "std_order_rate": 2, "min_order_rate": 5, "max_order_rate": 22},
    {"latitude": -6.9000, "longitude": 107.6000, "order_rate": 16, "mean_order_rate": 14, "std_order_rate": 3, "min_order_rate": 6, "max_order_rate": 25},
    {"latitude": -6.9100, "longitude": 107.6100, "order_rate": 15, "mean_order_rate": 13, "std_order_rate": 2, "min_order_rate": 5, "max_order_rate": 23},
    

    {"latitude": -6.8600, "longitude": 107.5600, "order_rate": 9, "mean_order_rate": 7, "std_order_rate": 1, "min_order_rate": 2, "max_order_rate": 15},
    {"latitude": -6.8500, "longitude": 107.5500, "order_rate": 6, "mean_order_rate": 4, "std_order_rate": 1, "min_order_rate": 1, "max_order_rate": 10},
    {"latitude": -6.8400, "longitude": 107.5400, "order_rate": 5, "mean_order_rate": 3, "std_order_rate": 1, "min_order_rate": 1, "max_order_rate": 8},
    {"latitude": -6.8300, "longitude": 107.5300, "order_rate": 4, "mean_order_rate": 2, "std_order_rate": 1, "min_order_rate": 1, "max_order_rate": 6},
    {"latitude": -6.8200, "longitude": 107.5200, "order_rate": 3, "mean_order_rate": 1, "std_order_rate": 1, "min_order_rate": 1, "max_order_rate": 5},
    

    {"latitude": -6.9300, "longitude": 107.6300, "order_rate": 10, "mean_order_rate": 8, "std_order_rate": 2, "min_order_rate": 2, "max_order_rate": 16},
    {"latitude": -6.9400, "longitude": 107.6400, "order_rate": 8, "mean_order_rate": 6, "std_order_rate": 1, "min_order_rate": 2, "max_order_rate": 14},
    {"latitude": -6.9500, "longitude": 107.6500, "order_rate": 9, "mean_order_rate": 7, "std_order_rate": 1, "min_order_rate": 2, "max_order_rate": 15},
    {"latitude": -6.9600, "longitude": 107.6600, "order_rate": 7, "mean_order_rate": 5, "std_order_rate": 1, "min_order_rate": 1, "max_order_rate": 12},
    {"latitude": -6.9700, "longitude": 107.6700, "order_rate": 6, "mean_order_rate": 4, "std_order_rate": 1, "min_order_rate": 1, "max_order_rate": 10},
    

    {"latitude": -6.8750, "longitude": 107.5750, "order_rate": 11, "mean_order_rate": 9, "std_order_rate": 2, "min_order_rate": 3, "max_order_rate": 18},
    {"latitude": -6.8850, "longitude": 107.5850, "order_rate": 12, "mean_order_rate": 10, "std_order_rate": 2, "min_order_rate": 3, "max_order_rate": 19},
    {"latitude": -6.8950, "longitude": 107.5950, "order_rate": 13, "mean_order_rate": 11, "std_order_rate": 2, "min_order_rate": 4, "max_order_rate": 20},
    {"latitude": -6.9050, "longitude": 107.6050, "order_rate": 14, "mean_order_rate": 12, "std_order_rate": 2, "min_order_rate": 5, "max_order_rate": 22},
    {"latitude": -6.9150, "longitude": 107.6150, "order_rate": 15, "mean_order_rate": 13, "std_order_rate": 2, "min_order_rate": 5, "max_order_rate": 23},
    

    {"latitude": -6.8675, "longitude": 107.5675, "order_rate": 8, "mean_order_rate": 6, "std_order_rate": 1, "min_order_rate": 2, "max_order_rate": 14},
    {"latitude": -6.8575, "longitude": 107.5575, "order_rate": 7, "mean_order_rate": 5, "std_order_rate": 1, "min_order_rate": 1, "max_order_rate": 12},
    {"latitude": -6.8475, "longitude": 107.5475, "order_rate": 6, "mean_order_rate": 4, "std_order_rate": 1, "min_order_rate": 1, "max_order_rate": 10},
    {"latitude": -6.8375, "longitude": 107.5375, "order_rate": 5, "mean_order_rate": 3, "std_order_rate": 1, "min_order_rate": 1, "max_order_rate": 8},
    {"latitude": -6.8275, "longitude": 107.5275, "order_rate": 4, "mean_order_rate": 2, "std_order_rate": 1, "min_order_rate": 1, "max_order_rate": 6},
    {"latitude": -6.9225, "longitude": 107.6225, "order_rate": 9, "mean_order_rate": 7, "std_order_rate": 1, "min_order_rate": 2, "max_order_rate": 15},
    {"latitude": -6.9325, "longitude": 107.6325, "order_rate": 8, "mean_order_rate": 6, "std_order_rate": 1, "min_order_rate": 2, "max_order_rate": 14},
    {"latitude": -6.9425, "longitude": 107.6425, "order_rate": 7, "mean_order_rate": 5, "std_order_rate": 1, "min_order_rate": 1, "max_order_rate": 12},
    {"latitude": -6.9525, "longitude": 107.6525, "order_rate": 6, "mean_order_rate": 4, "std_order_rate": 1, "min_order_rate": 1, "max_order_rate": 10},
    {"latitude": -6.9625, "longitude": 107.6625, "order_rate": 5, "mean_order_rate": 3, "std_order_rate": 1, "min_order_rate": 1, "max_order_rate": 8},
    {"latitude": -6.8725, "longitude": 107.5725, "order_rate": 10, "mean_order_rate": 8, "std_order_rate": 2, "min_order_rate": 2, "max_order_rate": 16},
    {"latitude": -6.8825, "longitude": 107.5825, "order_rate": 11, "mean_order_rate": 9, "std_order_rate": 2, "min_order_rate": 3, "max_order_rate": 18},
    {"latitude": -6.8925, "longitude": 107.5925, "order_rate": 12, "mean_order_rate": 10, "std_order_rate": 2, "min_order_rate": 3, "max_order_rate": 19},
    {"latitude": -6.9025, "longitude": 107.6025, "order_rate": 13, "mean_order_rate": 11, "std_order_rate": 2, "min_order_rate": 4, "max_order_rate": 20},
    {"latitude": -6.9125, "longitude": 107.6125, "order_rate": 14, "mean_order_rate": 12, "std_order_rate": 2, "min_order_rate": 5, "max_order_rate": 22},
    {"latitude": -6.8650, "longitude": 107.5650, "order_rate": 7, "mean_order_rate": 5, "std_order_rate": 1, "min_order_rate": 1, "max_order_rate": 12},
    {"latitude": -6.8550, "longitude": 107.5550, "order_rate": 6, "mean_order_rate": 4, "std_order_rate": 1, "min_order_rate": 1, "max_order_rate": 10},
    {"latitude": -6.8450, "longitude": 107.5450, "order_rate": 5, "mean_order_rate": 3, "std_order_rate": 1, "min_order_rate": 1, "max_order_rate": 8},
    {"latitude": -6.8350, "longitude": 107.5350, "order_rate": 4, "mean_order_rate": 2, "std_order_rate": 1, "min_order_rate": 1, "max_order_rate": 6},
    {"latitude": -6.8250, "longitude": 107.5250, "order_rate": 3, "mean_order_rate": 1, "std_order_rate": 1, "min_order_rate": 1, "max_order_rate": 5}
]

AREA_DATA = {}
_update_lock = threading.Lock()
_thread_running = True


AREA_DATA_INPUT = AREA_DATA_INPUT_100_AREA
if(AREA_USE == "area_data_input_100_area"):
    AREA_DATA_INPUT = AREA_DATA_INPUT_100_AREA
elif(AREA_USE == "area_data_input_200_area"):
    AREA_DATA_INPUT = AREA_DATA_INPUT_100_AREA
elif(AREA_USE == "area_data_input_500_area"):
    AREA_DATA_INPUT = AREA_DATA_INPUT_100_AREA
elif(AREA_USE == "area_data_input_1000_area"):
    AREA_DATA_INPUT = AREA_DATA_INPUT_100_AREA


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

import numpy as np

def random_area_order_rate():
    
    logger.info("Starting area order rate update thread")

    while _thread_running:
        try:
            with _update_lock:
                for area_node_id, data in AREA_DATA.items():
                    min_range = data["min_order_rate"]
                    max_range = data["max_order_rate"]
                    mean = data["mean_order_rate"]


                    sampled_rate = np.random.poisson(lam=mean)


                    new_order_rate = max(min_range, min(sampled_rate, max_range))


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
        lat_min = min(coordAwal[0], coordAkhir[0])
        lat_max = max(coordAwal[0], coordAkhir[0])
        lon_min = min(coordAwal[1], coordAkhir[1])
        lon_max = max(coordAwal[1], coordAkhir[1])

        cumulative_order_rate = 0
        visited_areas = set()

        for node_id, area_data in AREA_DATA.items():
            lat = area_data["area_lat"]
            lon = area_data["area_lon"]

            if lat_min <= lat <= lat_max and lon_min <= lon <= lon_max:
                if node_id not in visited_areas:
                    cumulative_order_rate += area_data.get("area_order_rate", 0)
                    visited_areas.add(node_id)

        return cumulative_order_rate

    except Exception as e:
        print(f"Error calculating cumulative order rate: {str(e)}")
        return 0

def stop_background_thread():
    
    global _thread_running
    _thread_running = False
