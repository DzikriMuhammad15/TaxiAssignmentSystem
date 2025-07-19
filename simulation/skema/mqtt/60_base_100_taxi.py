
import osmnx as ox
import networkx as nx
from shapely.geometry import LineString, Point
import time
import json
import numpy as np
import simpy
import random
import threading
import polyline
from geopy.distance import geodesic
import math
from collections import defaultdict
from functools import lru_cache
import heapq
import json
import zlib
import base64
import pickle
import paho.mqtt.client as mqtt
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timedelta

class StopTimer:
    def __init__(self, env, is_stop=False, current_time=0):
        self.env = env
        self.is_stop = is_stop
        self.current_time = current_time
        self.real_time_start = time.time()

    def count_time(self):
        while True:
            if not self.is_stop:
                yield self.env.timeout(1)
                self.current_time = self.current_time + 1
            else:
                yield self.env.timeout(0.1)
    
    def timeout(self, timeout_duration):

        return self.env.timeout(timeout_duration)
    
    def stop_timer(self):
        
        self.is_stop = True
        debug_timer("️  Timer STOPPED - waiting for server response")
    
    def resume_timer(self, real_wait_time_seconds):
        

        simulation_time_to_add = real_wait_time_seconds / 60.0
        
        debug_timer(f"️  Timer RESUMED - adding {simulation_time_to_add:.2f} simulation time units for {real_wait_time_seconds:.2f}s real wait")
        

        self.current_time += simulation_time_to_add
        

        self.is_stop = False


ALPHA_T = 0.00024524
ALPHA_D = 0
SIMULATION_SPEEDUP = 10


MQTT_BROKER = "localhost"
MQTT_PORT = 8883
MQTT_KEEPALIVE = 60


TOPIC_ASSIGNMENT_REQUEST = "taxi/assignment/request"
TOPIC_ASSIGNMENT_RESPONSE = "taxi/assignment/response"


mqtt_client = None
simulation_object = None
assignment_response_received = False
assignment_response_data = None
request_start_time = None


assignment_stats = {
    'total_assignments': 0,
    'successful_arrivals': 0,
    'travel_times': [],
    'travel_distances': [],
    'assignment_start_times': {},
    'assignment_routes': {},
    'server_response_times': []
}


base_order_stats = {
    'total_orders_generated': 0,
    'orders_served_successfully': 0,
    'orders_failed_no_taxis': 0,
    'orders_by_base': {}
}


hourly_stats = {
    'orders_appeared': [0] * 24,
    'orders_served': [0] * 24,
    'orders_failed': [0] * 24,
    'assignments_made': [0] * 24,
    'taxi_utilization': [0] * 24
}

detailed_stats = {
    'successful_order_durations': [],
    'successful_order_distances': [],
    'hourly_assignments': [0] * 24,
    'base_performance': {},
    'congestion_samples': [],
    'taxi_utilization_samples': [],
    'peak_hours': [],
    'service_quality_by_hour': [],
    'distance_by_base': {},
    'duration_by_base': {},
    'battery_usage_stats': [],
    'interception_stats': [],
}

def get_current_hour(simulation_time):
    return int(simulation_time / 60) % 24

def track_hourly_order(simulation_time, order_type):
    hour = get_current_hour(simulation_time)
    if order_type == 'appeared':
        hourly_stats['orders_appeared'][hour] += 1
    elif order_type == 'served':
        hourly_stats['orders_served'][hour] += 1
    elif order_type == 'failed':
        hourly_stats['orders_failed'][hour] += 1

def debug_assignment(message):
    
    print(f"[ASSIGNMENT] {message}")

def debug_error(message):
    
    print(f"[ERROR] {message}")

def debug_mqtt(message):
    
    print(f"[MQTT] {message}")

def debug_timer(message):
    
    print(f"[TIMER] {message}")

def debug_congestion(message):
    
    print(f"[CONGESTION] {message}")


with open("bandung_drive_osm.pkl", "rb") as f:
    G = pickle.load(f)


def initialize_graph_attributes(G):
    
    debug_congestion("Initializing graph attributes...")
    
    for u, v, k, data in G.edges(keys=True, data=True):

        if "speed_kph" not in data:
            data["speed_kph"] = 30
        

        base_speed = data["speed_kph"]
        speed_mps = base_speed / 3.6
        length = data.get("length", 100)
        

        travel_time = length / speed_mps if speed_mps > 0 else float('inf')
        

        data["duration"] = travel_time
        data["congestion_level"] = 0
        data["speed_kph_congested"] = base_speed
        data["travel_time_congested"] = travel_time
    
    debug_congestion("Graph attributes initialized")

def update_congestion(G, mean=48, std=10):
    
    updated_edges = 0
    total_congestion = 0
    
    for u, v, k, data in G.edges(keys=True, data=True):
        base_speed = data.get("speed_kph", 30)
        

        congestion = np.clip(np.random.normal(mean, std), 0, 100)
        

        congested_speed = base_speed / (1 + congestion / 100)
        speed_mps = congested_speed / 3.6
        

        length = data.get("length", 100)
        travel_time = length / speed_mps if speed_mps > 0 else float('inf')
        

        data["congestion_level"] = congestion
        data["speed_kph_congested"] = congested_speed
        data["travel_time_congested"] = travel_time
        data["duration"] = travel_time
        
        updated_edges += 1
        total_congestion += congestion
    
    avg_congestion = total_congestion / updated_edges if updated_edges > 0 else 0
    debug_congestion(f"Updated {updated_edges} edges, average congestion: {avg_congestion:.1f}%")


initialize_graph_attributes(G)


nodes_array = np.array([(node, data['x'], data['y']) for node, data in G.nodes(data=True)], 
                      dtype=[('node', object), ('x', float), ('y', float)])


def node_id_to_string(node_id):
    
    return str(node_id)

def string_to_node_id(string_id):
    
    try:
        result = int(string_id)
        return result
    except (ValueError, TypeError):
        debug_error(f"Could not convert string ID '{string_id}' to integer")
        return string_id

def taxi_id_to_string(taxi_id):
    
    return str(taxi_id)

def string_to_taxi_id(string_id):
    
    return str(string_id)

def convert_to_int_array(string_array):
    
    try:
        result = [int(x) for x in string_array]
        return result
    except Exception as e:
        debug_error(f"Int conversion failed: {e}")
        return []

def decode_array(base64_str):
    
    if not base64_str:
        debug_error("Empty base64 string")
        return None
    
    try:
        compressed = base64.b64decode(base64_str)
        json_str = zlib.decompress(compressed).decode('utf-8')
        data_array = json.loads(json_str)
        return data_array
    except Exception as e:
        debug_error(f"Route decode failed: {e}")
        return None


@lru_cache(maxsize=10000)
def get_node_from_nearest_edge(lat, lon):
    
    u, v, key = ox.distance.nearest_edges(G, lon, lat)
    point = Point(lon, lat)
    
    node_u = G.nodes[u]
    node_v = G.nodes[v]
    
    dist_u = point.distance(Point(node_u['x'], node_u['y']))
    dist_v = point.distance(Point(node_v['x'], node_v['y']))
    
    return u if dist_u < dist_v else v


@lru_cache(maxsize=10000)
def get_node_lat_lon(node_id):
    
    node_data = G.nodes[node_id]
    return (node_data["y"], node_data["x"])


route_cache = {}
def clear_route_cache():
    
    global route_cache
    route_cache.clear()
    debug_congestion("Route cache cleared due to congestion update")

def get_route(init_node, dest_node):
    

    if isinstance(init_node, str):
        init_node = string_to_node_id(init_node)
    if isinstance(dest_node, str):
        dest_node = string_to_node_id(dest_node)
    
    cache_key = (init_node, dest_node)
    if cache_key in route_cache:
        return route_cache[cache_key]
    
    try:

        if init_node not in G.nodes():
            debug_error(f"Origin node {init_node} not in graph")
            return []
        
        if dest_node not in G.nodes():
            debug_error(f"Destination node {dest_node} not in graph")
            return []
        
        route = nx.shortest_path(G, init_node, dest_node, weight='duration')
        route_cache[cache_key] = route
        return route
        
    except nx.NetworkXNoPath:
        debug_error(f"No path between {init_node} and {dest_node}")
        route_cache[cache_key] = []
        return []
    except Exception as e:
        debug_error(f"Route calculation failed: {e}")
        route_cache[cache_key] = []
        return []


@lru_cache(maxsize=10000)
def get_nearest_node(lat, lon):
    
    node = ox.distance.nearest_nodes(G, float(lon), float(lat))
    return node


edge_cache = {}
def find_edges(u, v):
    
    cache_key = (u, v)
    if cache_key in edge_cache:
        return edge_cache[cache_key]
    
    for key, data in G[u][v].items():
        edge = (u, v, key, data)
        edge_cache[cache_key] = edge
        return edge
    
    return None


def simulate_edge(env, taxi, edge, send_interval=1):
    
    u, v, key, data = edge
    
    length = data["length"]
    duration_seconds = data["duration"]
    battery_drain = ALPHA_D * length + ALPHA_T * duration_seconds
    new_battery = taxi.battery - battery_drain
    
    if new_battery <= 0:
        return False
    

    simulation_time = duration_seconds / 60.0
    
    yield env.timeout(simulation_time)
    
    newLat = G.nodes[v]['y']
    newLon = G.nodes[v]['x']
    taxi.current_lat = newLat
    taxi.current_lon = newLon
    taxi.battery = new_battery
    
    return True


def simulate_route(env, taxi, route):
    
    for i in range(len(route)-1):
        u = route[i]
        v = route[i+1]
        
        edge = find_edges(u, v)
        if edge:
            battery_sufficient = yield from simulate_edge(env, taxi, edge, send_interval=1)
            if not battery_sufficient:
                return False
        else:
            debug_error(f"Taxi {taxi.id}: Edge not found {u}->{v}")
            return False
    
    return True


def on_mqtt_connect(client, userdata, flags, rc):
    
    if rc == 0:
        debug_mqtt("Connected to MQTT broker successfully")
        client.subscribe(TOPIC_ASSIGNMENT_RESPONSE)
        debug_mqtt(f"Subscribed to topic: {TOPIC_ASSIGNMENT_RESPONSE}")
    else:
        debug_error(f"Failed to connect to MQTT broker, return code {rc}")

def on_mqtt_message(client, userdata, msg):
    
    global assignment_response_received, assignment_response_data, request_start_time
    
    try:
        topic = msg.topic
        payload = json.loads(msg.payload.decode())
        
        debug_mqtt(f"Received MQTT message on topic: {topic}")
        
        if topic == TOPIC_ASSIGNMENT_RESPONSE:

            if request_start_time:
                response_time = time.time() - request_start_time
                assignment_stats['server_response_times'].append(response_time)
                debug_mqtt(f"Server response time: {response_time:.2f} seconds")
            
            assignment_response_data = payload
            assignment_response_received = True
        
    except Exception as e:
        debug_error(f"Error processing MQTT message: {e}")

def init_mqtt():
    
    global mqtt_client
    try:
        mqtt_client = mqtt.Client()
        mqtt_client.on_connect = on_mqtt_connect
        mqtt_client.on_message = on_mqtt_message
        
        mqtt_client.connect(MQTT_BROKER, MQTT_PORT, MQTT_KEEPALIVE)
        mqtt_client.loop_start()
        
        debug_mqtt("MQTT client initialized and started")
        return True
    except Exception as e:
        debug_error(f"Failed to initialize MQTT: {e}")
        return False

def send_assignment_request(simulation_obj):
    
    global assignment_response_received, assignment_response_data, request_start_time
    
    try:
        debug_mqtt("Preparing assignment request data...")
        

        assignment_response_received = False
        assignment_response_data = None
        request_start_time = time.time()
        

        simulation_obj.timer.stop_timer()
        

        taxi_data = {}
        for taxi in simulation_obj.all_fleets:
            if taxi.is_available and taxi.state == "kosong" and taxi.battery > 30:
                taxi_data[taxi.id] = {
                    "taxi_state": taxi.state,
                    "latitude": taxi.current_lat,
                    "longitude": taxi.current_lon,
                    "battery": taxi.battery
                }
        

        base_data = {}
        for base in simulation_obj.all_bases:
            base_data[str(base.node_id)] = {
                "latitude": base.latitude,
                "longitude": base.longitude,
                "fleet": base.base_fleet
            }
        
        payload = {
            "taxi_data": taxi_data,
            "base_data": base_data
        }
        
        debug_mqtt(f"Sending request with {len(taxi_data)} available taxis and {len(base_data)} bases")
        

        if mqtt_client and mqtt_client.is_connected():
            message = json.dumps(payload)
            mqtt_client.publish(TOPIC_ASSIGNMENT_REQUEST, message)
            debug_mqtt("Assignment request sent via MQTT")
            

            timeout_seconds = 600
            wait_start = time.time()
            
            while not assignment_response_received and (time.time() - wait_start) < timeout_seconds:
                time.sleep(0.1)
            

            actual_wait_time = time.time() - request_start_time
            
            if assignment_response_received:
                debug_mqtt(f"Received response after {actual_wait_time:.2f} seconds")
                

                simulation_obj.timer.resume_timer(actual_wait_time)
                

                assignments = assignment_response_data.get('assignments', [])
                if assignments:
                    handle_taxi_assignments(assignments, simulation_obj)
                
                return True
            else:
                debug_error("Timeout waiting for assignment response")

                simulation_obj.timer.resume_timer(actual_wait_time)
                return False
        else:
            debug_error("MQTT client not connected")

            simulation_obj.timer.resume_timer(0)
            return False
            
    except Exception as e:
        debug_error(f"MQTT request failed: {e}")

        if request_start_time:
            actual_wait_time = time.time() - request_start_time
            simulation_obj.timer.resume_timer(actual_wait_time)
        return False

def handle_taxi_assignments(assignments, simulation_object):
    
    try:
        debug_assignment(f"Processing {len(assignments)} assignments")
        
        for i, assignment in enumerate(assignments):
            current_hour = get_current_hour(simulation_object.timer.current_time)
            hourly_stats['assignments_made'][current_hour] += len(assignments)
            taxi_id = str(assignment.get("taxi_id"))
            assigned_base = assignment.get("assigned_base")
            encoded_route = assignment.get("encoded_route_node_id")
            

            if not taxi_id or not assigned_base:
                debug_error(f"Assignment {i+1}: Missing required data, taxi_id: {taxi_id}, assigned_base: {assigned_base}, encoded_route: {encoded_route}")
                continue

            taxi_object = simulation_object.get_taxi(taxi_id)
            if not taxi_object:
                debug_error(f"Taxi {taxi_id} not found")
                continue
            
            debug_assignment(f"Taxi {taxi_id} -> Base {assigned_base}")
            
            data = {
                "assigned_base": assigned_base,
                "encoded_route_node_id": encoded_route
            }
            
            taxi_object.handle_assign_base(data)
            
    except Exception as e:
        debug_error(f"Assignment handler failed: {e}")


base_data = [
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



area_data = [

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

pull_lat = -6.957587
pull_lon = 107.639437

def calculate_route_distance(route):
    
    if not route or len(route) < 2:
        return 0.0
    
    total_distance = 0.0
    for i in range(len(route) - 1):
        u = route[i]
        v = route[i + 1]
        
        try:

            u_data = G.nodes[u]
            v_data = G.nodes[v]
            
            u_coord = (u_data['y'], u_data['x'])
            v_coord = (v_data['y'], v_data['x'])
            

            distance = geodesic(u_coord, v_coord).kilometers
            total_distance += distance
        except:
            continue
    
    return total_distance

class Taxi:
    def __init__(self, G, env, env_var, id, state, is_available, current_lat, current_lon, current_battery, timer):
        self.env = env
        self.env_var = env_var
        self.G = G
        self.id = str(id)
        self.state = state
        self.is_available = is_available
        self.current_lat = current_lat
        self.current_lon = current_lon
        self.current_base = None
        self.battery = current_battery
        self.timer = timer

    def handle_assign_base(self, data):
        
        try:
            assigned_base = data.get("assigned_base")
            encoded_route = data.get("encoded_route_node_id")
            

            if not assigned_base:
                debug_error(f"Taxi {self.id}: Missing assignment data")
                return
            

            base_id = string_to_node_id(assigned_base)
            if(not encoded_route):
                route_node_id = [base_id]
            else:

                route_node_id = decode_array(encoded_route)
            if not route_node_id:
                debug_error(f"Taxi {self.id}: Route decode failed")
                return
            
            route_node_id = convert_to_int_array(route_node_id)
            if not route_node_id or len(route_node_id) < 1:
                debug_error(f"Taxi {self.id}: Invalid route length, route length: {len(route_node_id)}")
                return
            

            if not self.env_var.is_node_base(base_id):
                debug_error(f"Taxi {self.id}: Base {base_id} not found")
                return
            

            assignment_stats['total_assignments'] += 1
            assignment_stats['assignment_start_times'][self.id] = self.timer.current_time
            assignment_stats['assignment_routes'][self.id] = route_node_id
            
            debug_assignment(f"Taxi {self.id}: Starting movement to base {base_id}")
            

            self.env.process(self.go_to_base(route=route_node_id, base_id=base_id))
            
        except Exception as e:
            debug_error(f"Taxi {self.id}: Assignment failed - {e}")

    def go_to_base(self, route, base_id):
        
        try:

            if not self.env_var.is_node_base(base_id):
                debug_error(f"Taxi {self.id}: Base {base_id} invalid")
                return
            
            base = self.env_var.get_base(base_id)
            if not base:
                debug_error(f"Taxi {self.id}: Cannot get base {base_id}")
                return
            

            self.is_available = False
            self.state = f"menuju ke base {base.node_id}"
        

            tercegat, battery_sufficient = yield from self.move_cegat(route)
        
            if battery_sufficient:
                if not tercegat:

                    if self.id in assignment_stats['assignment_start_times']:
                        start_time = assignment_stats['assignment_start_times'][self.id]
                        travel_time = self.timer.current_time - start_time
                        assignment_stats['travel_times'].append(travel_time)
                    

                        if self.id in assignment_stats['assignment_routes']:
                            route_for_distance = assignment_stats['assignment_routes'][self.id]
                            distance = calculate_route_distance(route_for_distance)
                            assignment_stats['travel_distances'].append(distance)
                    

                        del assignment_stats['assignment_start_times'][self.id]
                        if self.id in assignment_stats['assignment_routes']:
                            del assignment_stats['assignment_routes'][self.id]
                
                    assignment_stats['successful_arrivals'] += 1
                
                    self.is_available = True
                    self.state = "kosong"
                    self.current_base = base_id
                    base.add_taxi(self)
                
                    debug_assignment(f"Taxi {self.id}: Arrived at base {base_id}")
                else:

                    if self.id in assignment_stats['assignment_start_times']:
                        del assignment_stats['assignment_start_times'][self.id]
                    if self.id in assignment_stats['assignment_routes']:
                        del assignment_stats['assignment_routes'][self.id]
                    debug_assignment(f"Taxi {self.id}: Intercepted during movement")
            else:

                if self.id in assignment_stats['assignment_start_times']:
                    del assignment_stats['assignment_start_times'][self.id]
                if self.id in assignment_stats['assignment_routes']:
                    del assignment_stats['assignment_routes'][self.id]
                debug_error(f"Taxi {self.id}: Battery depleted during movement")
            
        except Exception as e:
            debug_error(f"Taxi {self.id}: Movement failed - {e}")

    def move_cegat(self, route):
        
        try:
            if not route or len(route) < 1:
                debug_error(f"Taxi {self.id}: Invalid route")
                return False, False
            
            dikunjungi = set()
            
            for i in range(len(route)-1):
                u = route[i]
                v = route[i+1]
                
                if u not in dikunjungi and v not in dikunjungi:
                    dikunjungi.add(u)
                    dikunjungi.add(v)
                    

                    if u not in G.nodes() or v not in G.nodes():
                        debug_error(f"Taxi {self.id}: Invalid nodes {u}->{v}")
                        return False, False
                    

                    battery_sufficient = yield from self.move([u, v])
                    if not battery_sufficient:
                        debug_error(f"Taxi {self.id}: Battery insufficient at step {i+1}")
                        return False, False
                    

                    if self.env_var.is_node_area(v):
                        area_v = self.env_var.get_area(v)
                        kecegat_di_v, order = area_v.is_cegat()
                        
                        if kecegat_di_v:
                            route_to_dest = self.env_var.order_system.route(origin_node=v, destination_node=order.destination_node)
                            self.env.process(self.handle_cegat(route=route_to_dest))
                            return True, True
            
            return False, True
            
        except Exception as e:
            debug_error(f"Taxi {self.id}: Move failed - {e}")
            return False, False

    def back_to_pull(self):
        pull_lat = self.env_var.pull.latitude
        pull_lon = self.env_var.pull.longitude
        pull_node = get_nearest_node(pull_lat, pull_lon)
        current_node = get_nearest_node(self.current_lat, self.current_lon)
        route = self.env_var.order_system.route(current_node, pull_node)
        battery_sufficient = yield from self.move(route=route)
    
    def handle_cegat(self, route):
        self.state = "bersama penumpang"
        
        battery_sufficient = yield from self.move(route)
        if(battery_sufficient):
            self.state = "kosong"
            self.is_available = True
            
            if self.battery < 30:
                yield from self.back_to_pull()

    def get_nearest_current_node(self):
        return get_nearest_node(self.current_lat, self.current_lon)

    def move(self, route):
        battery_sufficient = yield from simulate_route(self.timer, self, route)
        return battery_sufficient

    def handle_online_order(self, route_to_order_origin_node, route_to_order_destination_node):
        self.state = "menuju penumpang"
        self.is_available = False
        
        battery_sufficient = yield from self.move(route_to_order_origin_node)
        
        if(battery_sufficient):
            self.state = "bersama penumpang"

            battery_sufficient = yield from self.move(route_to_order_destination_node)
            
            if(battery_sufficient):
                self.state = "kosong"
                self.is_available = True
                
                if self.battery < 30:
                    yield from self.back_to_pull()

    def handle_base_order(self, route):
        self.state = "bersama penumpang"
        prev_base = self.current_base
        self.current_base = None
        self.is_available = False
        
        battery_sufficient = yield from self.move(route)
        
        if(battery_sufficient):
            self.state = "kosong"
            self.is_available = True
            
            if self.battery < 30:
                yield from self.back_to_pull()

class Order:
    def __init__(self, env, origin_node, destination_node):
        self.env = env
        self.origin_node = origin_node
        self.destination_node = destination_node

class Base:
    def __init__(self, env, G, env_var, node_id, capacity, order_rate, min_order_rate, max_order_rate, std_order_rate, mean_order_rate, timer):
        self.env = env
        self.G = G
        self.env_var = env_var
        self.node_id = node_id
        latitude, longitude = get_node_lat_lon(node_id)
        self.latitude = latitude
        self.longitude = longitude
        self.base_fleet = [None] * capacity
        self.order_rate = order_rate
        self.min_order_rate = min_order_rate
        self.max_order_rate = max_order_rate
        self.std_order_rate = std_order_rate
        self.mean_order_rate = mean_order_rate
        self.timer = timer
    
    def random_base_order_rate(self):
        while True:
            new_order_rate = max(self.min_order_rate, min(int(round(random.gauss(self.mean_order_rate, self.std_order_rate))), self.max_order_rate))
            self.order_rate = new_order_rate
            yield self.timer.timeout(60)

    def simulate_base_orders(self):
        while True:
            while self.timer.is_stop:
                yield self.env.timeout(1)
            jarak_antar_order = math.floor(60 / self.order_rate)
            yield self.timer.timeout(jarak_antar_order)
        

            track_hourly_order(self.timer.current_time, 'appeared')
            base_order_stats['total_orders_generated'] += 1
            if str(self.node_id) not in base_order_stats['orders_by_base']:
                base_order_stats['orders_by_base'][str(self.node_id)] = {
                    'generated': 0, 'served': 0, 'failed': 0
                }
            base_order_stats['orders_by_base'][str(self.node_id)]['generated'] += 1
        

            available_taxis = [i for i, taxi_id in enumerate(self.base_fleet) if taxi_id is not None]
            if not available_taxis:

                base_order_stats['orders_failed_no_taxis'] += 1
                base_order_stats['orders_by_base'][str(self.node_id)]['failed'] += 1
                debug_assignment(f"Base {self.node_id}: Order failed - no taxis available")
                track_hourly_order(self.timer.current_time, 'failed')
                continue
            

            destination_node = random.choice(self.env_var.all_nodes)
            order = Order(env=self.env, origin_node=self.node_id, destination_node=destination_node)
            

            taxi_index = available_taxis[0]
            taxi = self.env_var.get_taxi_by_id(self.base_fleet[taxi_index])
            
            if taxi:

                base_order_stats['orders_served_successfully'] += 1
                base_order_stats['orders_by_base'][str(self.node_id)]['served'] += 1
                track_hourly_order(self.timer.current_time, 'served')
            

                order_route = self.env_var.order_system.route(origin_node=order.origin_node,
                                                          destination_node=order.destination_node)
            

                self.base_fleet[taxi_index] = None
            

                self.base_fleet.sort(key=lambda x: x is None)
            

                self.env.process(taxi.handle_base_order(order_route))
                debug_assignment(f"Base {self.node_id}: Order served by taxi {taxi.id}")
            else:

                base_order_stats['orders_failed_no_taxis'] += 1
                base_order_stats['orders_by_base'][str(self.node_id)]['failed'] += 1
                debug_assignment(f"Base {self.node_id}: Order failed - taxi not found")
            
    def add_taxi(self, taxi):
        for i in range(len(self.base_fleet)):
            if self.base_fleet[i] is None:
                self.base_fleet[i] = taxi.id
                return

class Pull:
    def __init__(self, lat, lon):
        nearest_node_id = get_nearest_node(lat, lon)
        node_object = G.nodes[nearest_node_id]
        self.latitude = node_object["y"]
        self.longitude = node_object["x"]

class Area:
    def __init__(self, env, env_var, G, node_id, order_rate, min_order_rate, max_order_rate, mean_order_rate, std_order_rate, timer):
        self.env = env
        self.env_var = env_var
        self.G = G
        self.node_id = node_id
        lat, lon = get_node_lat_lon(node_id)
        self.latitude = lat
        self.longitude = lon
        self.order_rate = order_rate
        self.min_order_rate = min_order_rate
        self.max_order_rate = max_order_rate
        self.std_order_rate = std_order_rate
        self.mean_order_rate = mean_order_rate
        self.order_queue = []
        self.timer = timer
        
    def random_area_order_rate(self):
        while True:
            new_order_rate = max(self.min_order_rate, min(int(round(random.gauss(self.mean_order_rate, self.std_order_rate))), self.max_order_rate))
            self.order_rate = new_order_rate
            yield self.timer.timeout(60)
    
    def simulate_area_orders(self):
        while True:
            jarak_antar_order = math.floor(60 / self.order_rate)
            yield self.timer.timeout(jarak_antar_order)
            
            destination_node = random.choice(self.env_var.all_nodes)
            order = Order(env=self.env, origin_node=self.node_id, destination_node=destination_node)
            self.order_queue.append(order)
    
    def is_cegat(self):
        if len(self.order_queue) > 0:
            order = self.order_queue.pop(0)
            return True, order
        else:
            return False, None

class OrderSystem:
    def __init__(self, G):
        self.G = G
    
    def route(self, origin_node, destination_node):
        return get_route(origin_node, destination_node)

class Simulation:
    def __init__(self, all_fleets, all_bases, all_areas, all_nodes, order_system, pull, timer):
        self.all_fleets = all_fleets
        self.all_bases = all_bases
        self.all_areas = all_areas
        self.all_nodes = all_nodes
        self.order_system = order_system
        self.pull = pull
        self.timer = timer
        

        self.taxi_index = {}
        self.base_index = {}
        self.area_index = {}
        
    def add_taxi(self, taxi):
        self.all_fleets.append(taxi)
        self.taxi_index[taxi.id] = taxi
        
    def add_base(self, base):
        self.all_bases.append(base)
        self.base_index[base.node_id] = base
        
    def add_area(self, area):
        self.all_areas.append(area)
        self.area_index[area.node_id] = area
    
    def get_taxi(self, taxi_id):
        
        return self.taxi_index.get(str(taxi_id))
    
    def get_taxi_by_id(self, taxi_id):
        
        return self.get_taxi(taxi_id)
    
    def get_base(self, base_id):
        
        if isinstance(base_id, str):
            base_id = string_to_node_id(base_id)
        return self.base_index.get(base_id)
    
    def get_area(self, area_id):
        
        if isinstance(area_id, str):
            area_id = string_to_node_id(area_id)
        return self.area_index.get(area_id)
    
    def is_node_base(self, node_id):
        
        if isinstance(node_id, str):
            node_id = string_to_node_id(node_id)
        return node_id in self.base_index
    
    def is_node_area(self, node_id):
        
        if isinstance(node_id, str):
            node_id = string_to_node_id(node_id)
        return node_id in self.area_index

def periodic_assignment_request(env_var):
    
    while True:
        try:
            debug_mqtt("Requesting taxi assignments from backend...")
            success = send_assignment_request(env_var)
            if success:
                debug_mqtt("Assignment request completed successfully")
            else:
                debug_mqtt("Assignment request failed")
        except Exception as e:
            debug_error(f"Error in periodic assignment request: {e}")
        

        yield env_var.timer.timeout(15)

def periodic_congestion_update(env_var):
    
    while True:
        try:

            yield env_var.timer.timeout(60)
            

            update_congestion(G)
            

            clear_route_cache()
            
        except Exception as e:
            debug_error(f"Error in periodic congestion update: {e}")

def init_simulation(env_var):

    env_var.order_system.env.process(env_var.timer.count_time())
    

    for base in env_var.all_bases:
        env_var.order_system.env.process(base.simulate_base_orders())
        env_var.order_system.env.process(base.random_base_order_rate())
    

    for area in env_var.all_areas:
        env_var.order_system.env.process(area.simulate_area_orders())
        env_var.order_system.env.process(area.random_area_order_rate())
    

    env_var.order_system.env.process(periodic_assignment_request(env_var))
    

    env_var.order_system.env.process(periodic_congestion_update(env_var))
    
    yield env_var.order_system.env.timeout(1)

def generate_simulation_visualizations():
    import os
    
    if not os.path.exists('60_base_100_taxi_result'):
        os.makedirs('60_base_100_taxi_result')
    
    print("Generating simulation visualizations...")
    
    plt.style.use('default')
    plt.rcParams.update({'font.size': 14})
    
    plt.figure(figsize=(12, 8))
    hours = list(range(24))
    plt.plot(hours, hourly_stats['orders_appeared'], 'b-', linewidth=3, label='Orders Appeared', marker='o', markersize=8)
    plt.plot(hours, hourly_stats['orders_served'], 'g-', linewidth=3, label='Orders Served', marker='s', markersize=8)
    plt.plot(hours, hourly_stats['orders_failed'], 'r-', linewidth=3, label='Orders Failed', marker='^', markersize=8)
    plt.xlabel('Hour of Day', fontsize=16, fontweight='bold')
    plt.ylabel('Number of Orders', fontsize=16, fontweight='bold')
    plt.title('Hourly Order Statistics', fontsize=18, fontweight='bold', pad=20)
    plt.legend(fontsize=14, loc='upper left')
    plt.grid(True, alpha=0.3)
    plt.xticks(range(0, 24, 2), fontsize=14)
    plt.yticks(fontsize=14)
    plt.tight_layout()
    plt.savefig('60_base_100_taxi_result/hourly_order_statistics.png', dpi=300, bbox_inches='tight', 
                facecolor='white', edgecolor='none')
    plt.close()
    
    plt.figure(figsize=(14, 8))
    base_names = []
    base_appeared = []
    base_served = []
    
    for base_id, stats in base_order_stats['orders_by_base'].items():
        base_name = f"Base {base_id}"
        for base_info in base_data:
            base_node = get_nearest_node(base_info['latitude'], base_info['longitude'])
            if str(base_node) == str(base_id):
                base_name = base_info['name'][:12] + "..." if len(base_info['name']) > 12 else base_info['name']
                break
        
        base_names.append(base_name)
        base_appeared.append(stats['generated'])
        base_served.append(stats['served'])
    
    x = np.arange(len(base_names))
    width = 0.35
    
    plt.bar(x - width/2, base_appeared, width, label='Orders Appeared', alpha=0.8, color='skyblue')
    plt.bar(x + width/2, base_served, width, label='Orders Served', alpha=0.8, color='lightgreen')
    plt.xlabel('Base', fontsize=16, fontweight='bold')
    plt.ylabel('Number of Orders', fontsize=16, fontweight='bold')
    plt.title('Base Order Performance', fontsize=18, fontweight='bold', pad=20)
    plt.xticks(x, base_names, rotation=60, ha='right', fontsize=12)
    plt.yticks(fontsize=14)
    plt.legend(fontsize=14)
    plt.grid(True, alpha=0.3, axis='y')
    plt.tight_layout()
    plt.savefig('60_base_100_taxi_result/base_order_performance.png', dpi=300, bbox_inches='tight', 
                facecolor='white', edgecolor='none')
    plt.close()
    
    plt.figure(figsize=(14, 8))
    service_rates = []
    for base_id, stats in base_order_stats['orders_by_base'].items():
        if stats['generated'] > 0:
            rate = (stats['served'] / stats['generated']) * 100
            service_rates.append(rate)
        else:
            service_rates.append(0)
    
    colors = ['green' if rate >= 90 else 'orange' if rate >= 80 else 'red' for rate in service_rates]
    bars = plt.bar(range(len(base_names)), service_rates, color=colors, alpha=0.7, edgecolor='black', linewidth=1)

    for i, (bar, rate) in enumerate(zip(bars, service_rates)):
        plt.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1, 
                f'{rate:.1f}%', ha='center', va='bottom', fontsize=12, fontweight='bold')
    
    plt.xlabel('Base', fontsize=16, fontweight='bold')
    plt.ylabel('Service Rate (%)', fontsize=16, fontweight='bold')
    plt.title('Service Rate by Base', fontsize=18, fontweight='bold', pad=20)
    plt.xticks(range(len(base_names)), base_names, rotation=60, ha='right', fontsize=12)
    plt.yticks(fontsize=14)
    plt.grid(True, alpha=0.3, axis='y')
    plt.ylim(0, 110)
    plt.tight_layout()
    plt.savefig('60_base_100_taxi_result/service_rate_by_base.png', dpi=300, bbox_inches='tight', 
                facecolor='white', edgecolor='none')
    plt.close()

def print_simulation_summary():
    
    print("\n" + "="*80)
    print("SIMULATION SUMMARY REPORT")
    print("="*80)
    print(f"Simulation Duration: {simulation_object.timer.current_time:.2f} time units")
    print(f"Number of Taxis: {JUMLAH_TAXI}")
    print(f"Number of Bases: {len(base_data)}")
    print(f"Number of Areas: {len(area_data)}")
    print("-"*80)
    
    print("TAXI ASSIGNMENT STATISTICS:")
    print(f"  Total Assignments: {assignment_stats['total_assignments']}")
    print(f"  Successful Arrivals: {assignment_stats['successful_arrivals']}")
    
    if assignment_stats['total_assignments'] > 0:
        success_rate = (assignment_stats['successful_arrivals'] / assignment_stats['total_assignments']) * 100
        print(f"  Success Rate: {success_rate:.2f}%")
    else:
        print(f"  Success Rate: 0.00%")
    
    print(f"  Failed/Intercepted: {assignment_stats['total_assignments'] - assignment_stats['successful_arrivals']}")
    
    print("-"*80)
    
    print("BASE ORDER STATISTICS:")
    print(f"  Total Orders Generated: {base_order_stats['total_orders_generated']}")
    print(f"  Orders Served Successfully: {base_order_stats['orders_served_successfully']}")
    print(f"  Orders Failed (No Taxis): {base_order_stats['orders_failed_no_taxis']}")
    
    if base_order_stats['total_orders_generated'] > 0:
        service_rate = (base_order_stats['orders_served_successfully'] / base_order_stats['total_orders_generated']) * 100
        print(f"  Service Rate: {service_rate:.2f}%")
    else:
        print(f"  Service Rate: 0.00%")
    
    print("-"*80)
    
    print("BASE ORDER BREAKDOWN BY BASE:")
    for base_id, stats in base_order_stats['orders_by_base'].items():
        generated = stats['generated']
        served = stats['served']
        failed = stats['failed']
        if generated > 0:
            base_service_rate = (served / generated) * 100
            print(f"  Base {base_id}: Generated={generated}, Served={served}, Failed={failed}, Rate={base_service_rate:.1f}%")
    
    print("="*80)
    print("END OF SIMULATION REPORT")
    print("="*80 + "\n")
    generate_simulation_visualizations()

if __name__ == '__main__':
    print("Starting simulation with MQTT communication, artificial timer, and dynamic congestion...")


    if not init_mqtt():
        print("Failed to initialize MQTT, exiting...")
        exit(1)


    env = simpy.rt.RealtimeEnvironment(initial_time=0, factor=1.0, strict=False)
    timer = StopTimer(env=env)
    

    all_fleets = []
    all_bases = []
    all_areas = []
    all_nodes = list(G.nodes)
    

    pull = Pull(lat=pull_lat, lon=pull_lon)
    

    order_system = OrderSystem(G)
    order_system.env = env
    

    env_var = Simulation(all_fleets=all_fleets, all_bases=all_bases, 
                        all_areas=all_areas, all_nodes=all_nodes, 
                        order_system=order_system, pull=pull, timer=timer)
    

    simulation_object = env_var
    

    JUMLAH_TAXI = 100
    print(f"Creating {JUMLAH_TAXI} taxis...")
    

    for i in range(JUMLAH_TAXI):
        taxi = Taxi(G=G, env=env, env_var=env_var, id=str(i), 
                   state="kosong", is_available=True, 
                   current_lat=pull.latitude, current_lon=pull.longitude, 
                   current_battery=100, timer=timer)
        env_var.add_taxi(taxi)
    

    print(f"Creating {len(base_data)} bases...")
    for i, base_info in enumerate(base_data):
        lat = base_info.get("latitude")
        lon = base_info.get("longitude")
        capacity = base_info.get("capacity")
        
        base_node = get_nearest_node(lat, lon)
        
        base = Base(env=env, G=G, env_var=env_var, node_id=base_node, 
                   capacity=capacity, order_rate=base_info.get("order_rate"),
                   min_order_rate=base_info.get("min_order_rate", 0),
                   max_order_rate=base_info.get("max_order_rate", 50),
                   std_order_rate=base_info.get("std_order_rate", 1),
                   mean_order_rate=base_info.get("mean_order_rate", 10), timer=timer)
        env_var.add_base(base)
    

    print(f"Creating areas...")
    for i, area_info in enumerate(area_data[:20]):
        lat = area_info.get("latitude")
        lon = area_info.get("longitude")
        
        area_node = get_nearest_node(lat, lon)
        
        area = Area(env=env, env_var=env_var, G=G, node_id=area_node,
                   order_rate=area_info.get("order_rate"),
                   min_order_rate=area_info.get("min_order_rate", 0),
                   max_order_rate=area_info.get("max_order_rate", 50),
                   std_order_rate=area_info.get("std_order_rate", 1),
                   mean_order_rate=area_info.get("mean_order_rate", 10), timer=timer)
        env_var.add_area(area)
    

    print("Starting simulation with MQTT communication, artificial timer, and dynamic congestion...")
    print(f"MQTT Topics: Request={TOPIC_ASSIGNMENT_REQUEST}, Response={TOPIC_ASSIGNMENT_RESPONSE}")
    env.process(init_simulation(env_var=env_var))
    
    try:

        while env_var.timer.current_time < 1440:
            env.step()

            time.sleep(0.001)
    
        print(f"Simulation completed at timer time: {env_var.timer.current_time}")
    finally:

        if mqtt_client:
            mqtt_client.loop_stop()
            mqtt_client.disconnect()

    print_simulation_summary()
