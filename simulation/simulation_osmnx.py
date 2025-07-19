import osmnx as ox
import networkx as nx
from shapely.geometry import LineString, Point
import time
import json
import paho.mqtt.client as mqtt
import numpy as np
import simpy
import random
import socketio
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
import threading


ALPHA_T = 0.00024524
ALPHA_D = 0
SIMULATION_SPEEDUP = 10


with open("bandung_drive_osm.pkl", "rb") as f:
    G = pickle.load(f)


edges_fixed = 0
for u, v, k, data in G.edges(keys=True, data=True):
    if 'duration' not in data:
        data['duration'] = data['length'] / 60
    else:
        try:
            data['duration'] = float(data['duration'])
        except (ValueError, TypeError):
            data['duration'] = data['length'] / 60
            edges_fixed += 1
    try:
        data['length'] = float(data['length'])
    except (ValueError, TypeError):
        data['length'] = 100.0
        edges_fixed += 1

def diagnose_graph_data():
    print("\nDIAGNOSING GRAPH DATA:")
    print("=" * 50)
    

    sample_nodes = list(G.nodes())[:5]
    print("Sample node types:")
    for node in sample_nodes:
        print(f"  Node {node}: {type(node)}")
    

    sample_edges = list(G.edges(keys=True, data=True))[:5]
    print("\nSample edge data types:")
    for u, v, k, data in sample_edges:
        print(f"  Edge {u}->{v}:")
        print(f"    length: {data.get('length')} ({type(data.get('length'))})")
        print(f"    duration: {data.get('duration')} ({type(data.get('duration'))})")
    

    problematic_edges = 0
    string_durations = 0
    string_lengths = 0
    
    for u, v, k, data in G.edges(keys=True, data=True):
        if isinstance(data.get('duration'), str):
            string_durations += 1
        if isinstance(data.get('length'), str):
            string_lengths += 1
        if not isinstance(data.get('duration'), (int, float)) or not isinstance(data.get('length'), (int, float)):
            problematic_edges += 1
    
    print(f"\nEdge data analysis:")
    print(f"  Total edges: {G.number_of_edges()}")
    print(f"  Edges with string durations: {string_durations}")
    print(f"  Edges with string lengths: {string_lengths}")
    print(f"  Problematic edges: {problematic_edges}")
    
    if problematic_edges == 0:
        print("All edge data types are correct!")
    else:
        print(f"Found {problematic_edges} edges with data type issues")
    
    print("=" * 50)

print("Building spatial index...")
nodes_array = np.array([(node, data['x'], data['y']) for node, data in G.nodes(data=True)], 
                      dtype=[('node', object), ('x', float), ('y', float)])

def node_id_to_string(node_id):
    return str(node_id)

def string_to_node_id(string_id):
    try:
        return int(string_id)
    except (ValueError, TypeError):
        print(f"Warning: Could not convert string ID '{string_id}' to integer")
        return string_id

def taxi_id_to_string(taxi_id):
    return str(taxi_id)

def string_to_taxi_id(string_id):
    return str(string_id)

def handle_taxi_assignment(payload, simulation_object):
    array_of_assignments = payload.get("message")
    print(f"array of taxi assignments: {len(array_of_assignments)}")
    for assignment in array_of_assignments:
        taxi_id = str(assignment.get("taxi_id"))
        data = {}
        data["assigned_base"] = assignment.get("assigned_base")
        data["encoded_route_node_id"] = assignment.get("encoded_route_node_id")

        taxi_object = simulation_object.get_taxi(taxi_id)
        taxi_object.handle_assign_base(data)

class DirectMQTTClient:
    def __init__(self, broker, port, simulation_object):
        self.client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
        self.broker = broker
        self.port = port
        self.subscriptions = {}
        self.simulation_object = simulation_object


        self.client.on_message = self._on_message
        self.client.on_disconnect = self._on_disconnect
        self.client.reconnect_delay_set(min_delay=1, max_delay=60)

    def connect(self):
        self.client.connect(self.broker, self.port, 60)
        threading.Thread(target=self.client.loop_forever, daemon=True, name="MQTTThread").start()

    def _on_disconnect(self, client, userdata, rc):
        if rc != 0:
            print(f"Koneksi MQTT terputus (rc={rc}), mencoba reconnect...")

    def publish(self, topic, payload):
        self.client.publish(topic, payload)

    def subscribe(self, topic, handler):
        self.subscriptions[topic] = handler
        self.client.subscribe(topic)

    def _on_message(self, client, userdata, message):
        topic = message.topic
        payload = json.loads(message.payload.decode())
        if topic in self.subscriptions:
            handler = self.subscriptions[topic]
            handler(payload, self.simulation_object)
        else:
            print(f"Tidak ada handler untuk topik: {topic}, payload: {payload}")



broker = "localhost"
mqtt_port = 8883


topic_gps = "gps/tracker"
topic_base_request = "request/base"
topic_base_change = "state/base"
topic_base_register = "register/base"
topic_taxi_assignmet = "assignment/taxi"


def convert_to_int_array(string_array):
    return [int(x) for x in string_array]

def decode_array(base64_str, base_id):
    try:
        compressed = base64.b64decode(base64_str)
        json_str = zlib.decompress(compressed).decode('utf-8')
        data_array = json.loads(json_str)   
        return data_array
    except Exception:
        print("exception decode array node")
        return [base_id]


@lru_cache(maxsize=10000)
def get_node_from_nearest_edge(lat, lon):
    u, v, key = ox.distance.nearest_edges(G, lon, lat)
    point = Point(lon, lat)
    node_u = G.nodes[u]
    node_v = G.nodes[v]
    
    dist_u = point.distance(Point(node_u['x'], node_u['y']))
    dist_v = point.distance(Point(node_v['x'], node_v['y']))
    
    return u if dist_u < dist_v else v


def send_mqtt(topic, dictionary, env=None):
    if env:
        dictionary["sim_time"] = env.now
    if "taxi_id" in dictionary:
        dictionary["taxi_id"] = taxi_id_to_string(dictionary["taxi_id"])
    if "base_id" in dictionary:
        dictionary["base_id"] = node_id_to_string(dictionary["base_id"])
    
    payload = json.dumps(dictionary)
    mqtt_client.publish(topic, payload)


@lru_cache(maxsize=10000)
def get_node_lat_lon(node_id):
    node_data = G.nodes[node_id]
    return (node_data["y"], node_data["x"])


route_cache = {}
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
            print(f"Warning: Origin node {init_node} not found in graph")
            return []
        
        if dest_node not in G.nodes():
            print(f"Warning: Destination node {dest_node} not found in graph")
            return []
        

        route = nx.shortest_path(G, init_node, dest_node, weight='duration')
        route_cache[cache_key] = route
        return route
        
    except nx.NetworkXNoPath:
        print(f"No path found between {init_node} and {dest_node}")
        route_cache[cache_key] = []
        return []
    except Exception as e:
        print(f"Error finding path between {init_node} and {dest_node}: {e}")
        print(f"Node types: {type(init_node)}, {type(dest_node)}")
        try:
            if init_node in G.nodes() and len(list(G.neighbors(init_node))) > 0:
                neighbor = list(G.neighbors(init_node))[0]
                edge_data = G[init_node][neighbor]
                print(f"Sample edge data from {init_node}: {edge_data}")
        except:
            pass
            
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
    duration = data["duration"]
    battery_drain = ALPHA_D * length + ALPHA_T * duration
    new_battery = taxi.battery - battery_drain
    
    if new_battery <= 0:
        yield env.timeout(1)
        return False
    
    total_simulation_time = duration / 60
    yield env.timeout(total_simulation_time)
    newLat = G.nodes[v]['y']
    newLon = G.nodes[v]['x']
    taxi.current_lat = newLat
    taxi.current_lon = newLon
    taxi.battery = new_battery
    payload_dict = {
            "taxi_id": taxi.id,
            "taxi_state": taxi.state,
            "latitude": newLat,
            "longitude": newLon,
            "battery": new_battery
        }
    # send_mqtt(topic_gps, payload_dict, env)
    return True, total_simulation_time

def simulate_route(env, taxi, route):
    cummulative_total_simulation_time = 0
    for i in range(len(route)-1):
        u = route[i]
        v = route[i+1]
        edge = find_edges(u, v)
        if edge:
            battery_sufficient, total_simulation_time = yield from simulate_edge(env, taxi, edge, send_interval=1)
            cummulative_total_simulation_time = cummulative_total_simulation_time + total_simulation_time
            if not battery_sufficient:
                print(f"Taxi {taxi.id} ran out of battery")
                return False
                break
        else:
            print(f"Edge not found between {u} and {v}")
    return True, cummulative_total_simulation_time

def travel(env, taxi, u, v, coordAwal=None, coordAkhir=None, type="nodeId"):
    if type == "nodeId":
        origin = u
        destination = v
    elif type == "coord":
        latAwal, lonAwal = coordAwal
        latAkhir, lonAkhir = coordAkhir
        origin = get_nearest_node(latAwal, lonAwal)
        destination = get_nearest_node(latAkhir, lonAkhir)
    else:
        print("Invalid type (use 'nodeId' or 'coord')")
        return
    
    route = get_route(origin, destination)
    battery_sufficient, cummulative_total_simulation_time = yield from simulate_route(env, taxi, route)

base_data = [
    {"name": "d'Botanica Pasteur", "latitude": -6.8812, "longitude": 107.5800, "capacity": 3, "order_rate": 12,  "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},
    {"name": "Cihampelas Walk (Ciwalk)", "latitude": -6.8938, "longitude": 107.6052, "capacity": 4, "order_rate": 11,  "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},
    {"name": "Paris Van Java (PVJ)", "latitude": -6.8895, "longitude": 107.5957, "capacity": 4, "order_rate": 15,  "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},
    {"name": "Bandung Indah Plaza (BIP)", "latitude": -6.9112, "longitude": 107.6097, "capacity": 3, "order_rate": 14,  "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},
    {"name": "Summarecon Mall Bandung", "latitude": -6.9600, "longitude": 107.7170, "capacity": 5, "order_rate": 13,  "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},
    {"name": "Trans Studio Mall Bandung", "latitude": -6.9276, "longitude": 107.6364, "capacity": 5, "order_rate": 20,  "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},


    {"name": "Stasiun Bandung", "latitude": -6.9175, "longitude": 107.6030, "capacity": 4, "order_rate": 18,  "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},
    {"name": "Stasiun Padalarang Whoosh", "latitude": -6.8375, "longitude": 107.4708, "capacity": 2, "order_rate": 6,  "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},
    {"name": "Stasiun Tegalluar Whoosh", "latitude": -6.9850, "longitude": 107.7400, "capacity": 2, "order_rate": 7,  "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},
    {"name": "Terminal Leuwipanjang", "latitude": -6.9333, "longitude": 107.5742, "capacity": 3, "order_rate": 10,  "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},
    {"name": "Kertajati Internasional Airport", "latitude": -6.5569, "longitude": 108.2314, "capacity": 6, "order_rate": 5,  "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},
    {"name": "Cititrans Dipatiukur", "latitude": -6.8840, "longitude": 107.6186, "capacity": 2, "order_rate": 9,  "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},
    {"name": "Shuttle Drop Off Pasteur", "latitude": -6.8855, "longitude": 107.5779, "capacity": 3, "order_rate": 8,  "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},


    {"name": "Majesty Apartement", "latitude": -6.8858, "longitude": 107.5790, "capacity": 2, "order_rate": 6,  "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},
    {"name": "Kota Baru Parahyangan", "latitude": -6.8655, "longitude": 107.4750, "capacity": 3, "order_rate": 7,  "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},


    {"name": "W Super Club", "latitude": -6.9180, "longitude": 107.6150, "capacity": 2, "order_rate": 9,  "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},
    {"name": "MOD Pool and Club", "latitude": -6.9205, "longitude": 107.6162, "capacity": 2, "order_rate": 10,  "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},


    {"name": "Dusun Bambu", "latitude": -6.7904, "longitude": 107.5950, "capacity": 2, "order_rate": 7,  "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},
    {"name": "Lembang Park Zoo", "latitude": -6.8247, "longitude": 107.6133, "capacity": 2, "order_rate": 6,  "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},
    {"name": "The Lodge Maribaya", "latitude": -6.8012, "longitude": 107.6857, "capacity": 2, "order_rate": 5,  "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},


    {"name": "Komplek Pemerintahan Kab. Bandung (Soreang)", "latitude": -7.0223, "longitude": 107.5186, "capacity": 3, "order_rate": 8,  "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},


    {"name": "Rest Area Alun-Alun Lembang", "latitude": -6.8180, "longitude": 107.6169, "capacity": 2, "order_rate": 4,  "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50}
]




area_data = [
    {"latitude": -6.8904, "longitude": 107.6102, "order_rate": 5, 
        "mean_order_rate": 10,
        "std_order_rate": 1,
        "min_order_rate": 0,
        "max_order_rate": 50, 
    },
    {
        "latitude": -6.92156,
        "longitude": 107.60766,
        "mean_order_rate": 10,
        "std_order_rate": 1,
        "min_order_rate": 0,
        "max_order_rate": 50,
        "order_rate": 7
    },
    {
        "latitude": -6.91417,
        "longitude": 107.60250,
        "mean_order_rate": 10,
        "std_order_rate": 1,
        "min_order_rate": 0,
        "max_order_rate": 50,
        "order_rate": 12
    },
    {
        "latitude": -6.921027,
        "longitude": 107.610027,
        "mean_order_rate": 10,
        "std_order_rate": 1,
        "min_order_rate": 0,
        "max_order_rate": 50,
        "order_rate": 9
    },
    {
        "latitude": -6.900306,
        "longitude": 107.618709,
        "mean_order_rate": 10,
        "std_order_rate": 1,
        "min_order_rate": 0,
        "max_order_rate": 50,
        "order_rate": 5
    },
    {
        "latitude": -6.91333,
        "longitude": 107.60778,
        "mean_order_rate": 10,
        "std_order_rate": 1,
        "min_order_rate": 0,
        "max_order_rate": 50,
        "order_rate": 6
    },
    {
        "latitude": -6.829484,
        "longitude": 107.596632,
        "mean_order_rate": 10,
        "std_order_rate": 1,
        "min_order_rate": 0,
        "max_order_rate": 50,
        "order_rate": 8
    },
    {
        "latitude": -6.8782,
        "longitude": 107.5930,
        "mean_order_rate": 10,
        "std_order_rate": 1,
        "min_order_rate": 0,
        "max_order_rate": 50,
        "order_rate": 12
    },
    {
        "latitude": -6.8967,
        "longitude": 107.6011,
        "mean_order_rate": 10,
        "std_order_rate": 1,
        "min_order_rate": 0,
        "max_order_rate": 50,
        "order_rate": 6
    },
    {
        "latitude": -6.9168,
        "longitude": 107.6215,
        "mean_order_rate": 10,
        "std_order_rate": 1,
        "min_order_rate": 0,
        "max_order_rate": 50,
        "order_rate": 7
    }
]


pull_lat = -6.957587
pull_lon = 107.639437


class Taxi:
    def __init__(self, G, env, env_var, id, state, is_available, current_lat, current_lon, current_battery):
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
        

    def handle_assign_base(self, data):
        base_id = string_to_node_id(data.get("assigned_base"))
        encoded_route_node_id = data.get("encoded_route_node_id")
        route_node_id = decode_array(encoded_route_node_id, base_id)
        route_node_id = convert_to_int_array(route_node_id)
        self.env.process(self.go_to_base(route=route_node_id, base_id=base_id))
    
    def back_to_pull(self):
        pull_lat = self.env_var.pull.latitude
        pull_lon = self.env_var.pull.longitude
        pull_node = get_nearest_node(pull_lat, pull_lon)
        current_node = get_nearest_node(self.current_lat, self.current_lon)
        route = self.env_var.order_system.route(current_node, pull_node)
        battery_sufficient, cummulative_total_simulation_time = yield from self.move(route=route)
        if(not battery_sufficient):
            print("tidak bisa kembali ke base karena batere habis")

    def send_periodic_mqtt_taxi_state(self):
        while True:
            payload_dict = {
                "taxi_id": self.id,
                "taxi_state": self.state,
                "latitude": self.current_lat,
                "longitude": self.current_lon,
                "battery": self.battery
            }
            send_mqtt(topic_gps, payload_dict, self.env)
            yield self.env.timeout(1)
    
    def go_to_base(self, route, base_id):
        is_node_base = self.env_var.is_node_base(base_id)
        if is_node_base:
            base = self.env_var.get_base(base_id)
            self.is_available = False
            self.state = f"menuju ke base {base.node_id}"


            payload_dict = {
                "taxi_id": self.id,
                "taxi_state": self.state,
                "latitude": self.current_lat,
                "longitude": self.current_lon,
                "battery": self.battery
            }
            # send_mqtt(topic_gps, payload_dict, self.env)
            
            tercegat, battery_sufficient, cummulative_total_simulation_time_dalam_cegat = yield from self.move_cegat(route)
            if(battery_sufficient):
                if not tercegat:
                    self.is_available = True
                    self.state = "kosong"
                    self.current_base = base_id
                    base.add_taxi(self)
                    

                    payload_dict = {
                        "taxi_id": self.id,
                        "taxi_state": self.state,
                        "latitude": self.current_lat,
                        "longitude": self.current_lon,
                        "battery": self.battery
                    }
                    print(f"assignment taxi {self.id} to base {base_id} has cummulative time of: {cummulative_total_simulation_time_dalam_cegat} with length of node {len(route)}")
                    # send_mqtt(topic_gps, payload_dict, self.env)
        else:
            print(f"Node {base_id} is not a base")
    
    def move_cegat(self, route):
        dikunjungi = set()
        cummulative_total_simulation_time_dalam_cegat = 0
        for i in range(len(route)-1):
            u = route[i]
            v = route[i+1]
            
            if u not in dikunjungi and v not in dikunjungi:
                dikunjungi.add(u)
                dikunjungi.add(v)
                battery_sufficient, cummulative_total_simulation_time = yield from self.move([u, v])
                cummulative_total_simulation_time_dalam_cegat = cummulative_total_simulation_time_dalam_cegat + cummulative_total_simulation_time
                if(not battery_sufficient):
                    tercegat = False
                    return tercegat, battery_sufficient, cummulative_total_simulation_time_dalam_cegat
                

                if self.env_var.is_node_area(v):
                    area_v = self.env_var.get_area(v)
                    kecegat_di_v, order = area_v.is_cegat()
                    
                    if kecegat_di_v:
                        print(f"Taxi {self.id} intercepted at node {v}")
                        route = self.env_var.order_system.route(origin_node=v, destination_node=order.destination_node)
                        self.env.process(self.handle_cegat(route=route))
                        return True, True, cummulative_total_simulation_time_dalam_cegat
        return False, True, cummulative_total_simulation_time_dalam_cegat
    
    def handle_cegat(self, route):
        self.state = "bersama penumpang"
        payload_dict = {
            "taxi_id": self.id,
            "taxi_state": self.state,
            "latitude": self.current_lat,
            "longitude": self.current_lon,
            "battery": self.battery
        }
        # send_mqtt(topic_gps, payload_dict, self.env)
        
        battery_sufficient, cummulative_total_simulation_time = yield from self.move(route)
        if(battery_sufficient):
            self.state = "kosong"
            self.is_available = True
            payload_dict = {
                "taxi_id": self.id,
                "taxi_state": self.state,
                "latitude": self.current_lat,
                "longitude": self.current_lon,
                "battery": self.battery
            }
            # send_mqtt(topic_gps, payload_dict, self.env)
            
            if self.battery < 30:
                yield from self.back_to_pull()

    def get_nearest_current_node(self):
        return get_nearest_node(self.current_lat, self.current_lon)

    def move(self, route):
        battery_sufficient, cummulative_total_simulation_time = yield from simulate_route(self.env, self, route)
        return battery_sufficient, cummulative_total_simulation_time

    def handle_online_order(self, route_to_order_origin_node, route_to_order_destination_node):
        self.state = "menuju penumpang"
        self.is_available = False
        
        # print(f"{self.env.now}: Taxi {self.id} heading to passenger at {route_to_order_origin_node[-1]}")
        payload_dict = {
            "taxi_id": self.id,
            "taxi_state": self.state,
            "latitude": self.current_lat,
            "longitude": self.current_lon,
            "battery": self.battery
        }
        # send_mqtt(topic_gps, payload_dict, self.env)
        
        battery_sufficient, cummulative_total_simulation_time = yield from self.move(route_to_order_origin_node)
        
        if(battery_sufficient):
            self.state = "bersama penumpang"
            payload_dict = {
                "taxi_id": self.id,
                "taxi_state": self.state,
                "latitude": self.current_lat,
                "longitude": self.current_lon,
                "battery": self.battery
            }
            # send_mqtt(topic_gps, payload_dict, self.env)

            # print(f"{self.env.now}: Taxi {self.id} with passenger at node {route_to_order_origin_node[-1]} heading to {route_to_order_destination_node[-1]}")
            battery_sufficient, cummulative_total_simulation_time = yield from self.move(route_to_order_destination_node)
            
            if(battery_sufficient):
                self.state = "kosong"
                self.is_available = True
                payload_dict = {
                    "taxi_id": self.id,
                    "taxi_state": self.state,
                    "latitude": self.current_lat,
                    "longitude": self.current_lon,
                    "battery": self.battery
                }
                # send_mqtt(topic_gps, payload_dict, self.env)
                
                # print(f"{self.env.now}: Taxi {self.id} completed order, now at node {route_to_order_destination_node[-1]}")
                if self.battery < 30:
                    yield from self.back_to_pull()

    def handle_base_order(self, route):
        self.state = "bersama penumpang"
        prev_base = self.current_base
        self.current_base = None
        self.is_available = False
        
        payload_dict = {
            "taxi_id": self.id,
            "taxi_state": self.state,
            "latitude": self.current_lat,
            "longitude": self.current_lon,
            "battery": self.battery
        }
        # send_mqtt(topic_gps, payload_dict, self.env)
        
        battery_sufficient, cummulative_total_simulation_time = yield from self.move(route)
        
        if(battery_sufficient):
            self.state = "kosong"
            self.is_available = True
            payload_dict = {
                "taxi_id": self.id,
                "taxi_state": self.state,
                "latitude": self.current_lat,
                "longitude": self.current_lon,
                "battery": self.battery
            }
            # send_mqtt(topic_gps, payload_dict, self.env)
            
            if self.battery < 30:
                yield from self.back_to_pull()


class Order:
    def __init__(self, env, origin_node, destination_node):
        self.env = env
        self.origin_node = origin_node
        self.destination_node = destination_node


class Base:
    def __init__(self, env, G, env_var, node_id, capacity, order_rate, min_order_rate, max_order_rate, std_order_rate, mean_order_rate):
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
    
    def send_periodic_mqtt_base_state(self):
        while True:
            payload_dict = {
                "base_id": self.node_id,
                "base_latitude": self.latitude,
                "base_longitude": self.longitude,
                "base_fleet": self.base_fleet,
            }
            send_mqtt(topic_base_change, payload_dict, self.env)
            yield self.env.timeout(5)
    
    def random_base_order_rate(self):
        while True:
            new_order_rate = max(self.min_order_rate, min(int(round(random.gauss(self.mean_order_rate, self.std_order_rate))), self.max_order_rate))
            self.order_rate = new_order_rate
            yield self.env.timeout(60)

    def simulate_base_orders(self):
        while True:
            jarak_antar_order = math.floor(60 / self.order_rate)
            yield self.env.timeout(jarak_antar_order)
            

            available_taxis = [i for i, taxi_id in enumerate(self.base_fleet) if taxi_id is not None]
            if not available_taxis:
                # print(f"{self.env.now}: Base at node {self.node_id} is empty, cannot fulfill order")
                continue
                

            destination_node = random.choice(self.env_var.all_nodes)
            order = Order(env=self.env, origin_node=self.node_id, destination_node=destination_node)
            
            # print(f"{self.env.now}: Order created at base node {self.node_id}")
            

            taxi_index = available_taxis[0]
            taxi = self.env_var.get_taxi_by_id(self.base_fleet[taxi_index])
            
            if taxi:

                order_route = self.env_var.order_system.route(origin_node=order.origin_node,
                                                          destination_node=order.destination_node)
                

                self.base_fleet[taxi_index] = None
                

                self.base_fleet.sort(key=lambda x: x is None)
                

                self.env.process(taxi.handle_base_order(order_route))
                

                payload = {
                    "base_id": self.node_id,
                    "request": 1
                }
                send_mqtt(topic_base_request, payload, self.env)
                
                payload_update_state = {
                    "base_id": self.node_id,
                    "base_latitude": self.latitude,
                    "base_longitude": self.longitude,
                    "base_fleet": self.base_fleet,
                }
                send_mqtt(topic_base_change, payload_update_state, self.env)

    def create_base_assignment_request(self):
        while True:
            empty_slots = self.base_fleet.count(None)
            if empty_slots > 0:
                payload_dict = {
                    "base_id": self.node_id,
                    "requests": empty_slots
                }
                send_mqtt(topic_base_request, payload_dict, self.env)
            
            yield self.env.timeout(60)

    def create_base_assignment_request_init(self):
        empty_slots = self.base_fleet.count(None)
        if empty_slots > 0:
            payload_dict = {
                "base_id": self.node_id,
                "requests": empty_slots
            }
            send_mqtt(topic_base_request, payload_dict, self.env)
            
            payload_dict = {
                "base_id": self.node_id,
                "base_latitude": self.latitude,
                "base_longitude": self.longitude,
                "base_fleet": self.base_fleet,
            }
            send_mqtt(topic_base_register, payload_dict, self.env)
            
    def add_taxi(self, taxi):
        for i in range(len(self.base_fleet)):
            if self.base_fleet[i] is None:
                self.base_fleet[i] = taxi.id
                # print(f"{self.env.now}: Taxi {taxi.id} added to base {self.node_id} in slot {i}")
                
                payload_update_state = {
                    "base_id": self.node_id,
                    "base_latitude": self.latitude,
                    "base_longitude": self.longitude,
                    "base_fleet": self.base_fleet,
                }
                send_mqtt(topic_base_change, payload_update_state, self.env)
                return
                
        # print(f"{self.env.now}: Base {self.node_id} is full, taxi {taxi.id} cannot be added")



class Pull:
    def __init__(self, lat, lon):
        nearest_node_id = get_nearest_node(lat, lon)
        node_object = G.nodes[nearest_node_id]
        self.latitude = node_object["y"]
        self.longitude = node_object["x"]




class Area:
    def __init__(self, env, env_var, G, node_id, order_rate, min_order_rate, max_order_rate, mean_order_rate, std_order_rate):
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
        self.order_offline = []
    
    def simulate_area(self):
        while True:
            jarak_antar_order = math.floor(60 / self.order_rate)
            yield self.env.timeout(1000000)
            

            destination_node = random.choice(self.env_var.all_nodes)
            order = Order(env=self.env, origin_node=self.node_id, destination_node=destination_node)
            
            # print(f"{self.env.now}: Order created at area node {self.node_id}")
            

            self.env_var.order_system.assign_order(order)
    
    def order_offline_new(self):
        while True:
            yield self.env.timeout(5)
            destination_node = random.choice(self.env_var.all_nodes)
            order = Order(env=self.env, origin_node=self.node_id, destination_node=destination_node)
            self.order_offline.append(order)
    
    def order_offline_timeout(self):
        while True:
            yield self.env.timeout(7)
            if(len(self.order_offline) > 0):
                self.order_offline = self.order_offline[1:]

    def is_cegat(self):
        if(len(self.order_offline) <= 0):
            return False, None
        else:
            order = self.order_offline[0]
            self.order_offline = self.order_offline[1:]
            return True, order



class Order_system:
    def __init__(self, env, G, env_var, order_queue):
        self.env = env
        self.G = G
        self.env_var = env_var
        self.order_queue = order_queue
        self.spatial_index = {}

    def add_queue(self, order):
        self.order_queue.append(order)
    
    def assign_order(self, order):

        all_fleets = self.env_var.all_fleets
        available_fleets = [taxi for taxi in all_fleets if taxi.is_available and taxi.battery > 30]
        
        if not available_fleets:
            # print(f"{self.env.now}: No available taxis for order at {order.origin_node}. Adding to queue.")
            self.add_queue(order)
            return
        

        order_lat, order_lon = get_node_lat_lon(order.origin_node)
        

        nearest_taxi = None
        min_distance = float('inf')
        
        for taxi in available_fleets:

            dx = 111000 * (taxi.current_lon - order_lon) * math.cos(math.radians((taxi.current_lat + order_lat) / 2))
            dy = 111000 * (taxi.current_lat - order_lat)
            distance = math.sqrt(dx*dx + dy*dy)
            
            if distance < min_distance:
                min_distance = distance
                nearest_taxi = taxi
        
        if nearest_taxi is None:
            # print(f"{self.env.now}: Could not find a suitable taxi for order at {order.origin_node}. Adding to queue.")
            self.add_queue(order)
            return
        

        try:
            taxi_current_node = nearest_taxi.get_nearest_current_node()
            order_origin_node = order.origin_node
            order_destination_node = order.destination_node
            
            # print(f"Calculating route from {taxi_current_node} to {order_origin_node}")
            route_to_order_origin_node = self.route(origin_node=taxi_current_node, destination_node=order_origin_node)
            
            if not route_to_order_origin_node:
                print(f"Could not find route to passenger. Adding order to queue.")
                self.add_queue(order)
                return
            
            route_to_order_destination_node = self.route(origin_node=order_origin_node, destination_node=order_destination_node)
            
            if not route_to_order_destination_node:
                print(f"Could not find route to destination. Adding order to queue.")
                self.add_queue(order)
                return
            

            self.env.process(nearest_taxi.handle_online_order(
                route_to_order_origin_node=route_to_order_origin_node,
                route_to_order_destination_node=route_to_order_destination_node
            ))
        except Exception as e:
            print(f"Error assigning order: {e}")
            self.add_queue(order)

    def route(self, origin_node, destination_node):
        
        try:
            return get_route(origin_node, destination_node)
        except Exception as e:
            print(f"Error in route calculation: {e}")
            print(f"Origin node: {origin_node} ({type(origin_node)})")
            print(f"Destination node: {destination_node} ({type(destination_node)})")
            return []




class Simulation:
    def __init__(self, all_fleets, all_bases, all_areas, all_nodes, order_system, pull):
        self.all_fleets = all_fleets
        self.all_bases = all_bases
        self.all_areas = all_areas
        self.all_nodes = all_nodes
        self.order_system = order_system
        self.node_marking_areas = []
        self.pull = pull
        

        self.area_index = {area.node_id: area for area in all_areas}
        self.base_index = {base.node_id: base for base in all_bases}
        self.taxi_index = {}

    def add_node_marking_areas(self, node_marking_area_object):
        self.node_marking_areas.append(node_marking_area_object)
    
    def add_taxi(self, taxi):
        self.all_fleets.append(taxi)
        self.taxi_index[taxi.id] = taxi
    
    def get_taxi(self, taxi_id):
        return self.taxi_index.get(str(taxi_id))

    def add_base(self, base):
        self.all_bases.append(base)
        self.base_index[base.node_id] = base

    def add_area(self, area):
        self.all_areas.append(area)
        self.area_index[area.node_id] = area
    
    def set_order_system(self, order_system):
        self.order_system = order_system

    def is_node_area(self, node_id):
        return node_id in self.area_index
    
    def get_area(self, node_id):
        return self.area_index.get(node_id)
    
    def is_node_base(self, node_id):
        return node_id in self.base_index
    
    def get_base(self, node_id):
        return self.base_index.get(node_id)
    
    def get_taxi_by_id(self, taxi_id):
        return self.taxi_index.get(taxi_id)
    
    def get_node_marking_area_object(self, node_marking_area_id):
        for node in self.node_marking_areas:
            if node.node_id == node_marking_area_id:
                return node
        return None

    def is_cegat(self, node_marking_area_id):
        node_marking_area_object = self.get_node_marking_area_object(node_marking_area_id)
        if node_marking_area_object is None:
            return False, None
        
        order = node_marking_area_object.order
        if order is None:
            return False, None
        
        return True, order




def init_simulation(env_var):
    all_bases = env_var.all_bases
    all_areas = env_var.all_areas
    
    print(f"Initializing {len(all_bases)} bases and {len(all_areas)} areas")
    

    for base in all_bases:
        env.process(base.simulate_base_orders())
        env.process(base.random_base_order_rate())
        base.create_base_assignment_request_init()
    

    for area in all_areas:
        env.process(area.simulate_area())
        env.process(area.order_offline_new())
        env.process(area.order_offline_timeout())
    

    for taxi in env_var.all_fleets:
        env.process(taxi.send_periodic_mqtt_taxi_state())
    
    yield env.timeout(0)

def debug_node_types():
    
    print("\nDEBUG: Node Types in Graph")
    print("-------------------------")
    sample_nodes = list(G.nodes())[:5]
    for node in sample_nodes:
        print(f"Node: {node}, Type: {type(node)}")
    print("-------------------------\n")

if __name__ == '__main__':


    env = simpy.rt.RealtimeEnvironment(initial_time=0, factor=1.0, strict=False)
    

    diagnose_graph_data()
    

    all_fleets = []
    all_bases = []
    all_areas = []
    all_nodes = list(G.nodes)
    

    pull = Pull(lat=pull_lat, lon=pull_lon)
    

    env_var = Simulation(all_fleets=all_fleets, all_bases=all_bases, all_areas=all_areas, all_nodes=all_nodes, order_system=None, pull=pull)



    JUMLAH_TAXI = 15000
    
    print(f"Creating {JUMLAH_TAXI} taxis...")
    

    for i in range(JUMLAH_TAXI):
        taxi = Taxi(G=G, env=env, env_var=env_var, id=str(i), state="kosong", is_available=True, current_lat=pull.latitude, current_lon=pull.longitude, current_battery=100)
        env_var.add_taxi(taxi)
    
    print(f"Creating {len(base_data)} bases...")
    

    for i in range(len(base_data)):
        lat = base_data[i].get("latitude")
        lon = base_data[i].get("longitude")
        capacity = base_data[i].get("capacity")
        order_rate = base_data[i].get("order_rate")
        min_order_rate = base_data[i].get("min_order_rate", 0)
        max_order_rate = base_data[i].get("max_order_rate", 50)
        std_order_rate = base_data[i].get("std_order_rate", 1)
        mean_order_rate = base_data[i].get("mean_order_rate", 10)
        
        base_node = get_nearest_node(lat, lon)
        base = Base(env=env, G=G, env_var=env_var, node_id=base_node, capacity=capacity, order_rate=order_rate, 
                   min_order_rate=min_order_rate, max_order_rate=max_order_rate, std_order_rate=std_order_rate, 
                   mean_order_rate=mean_order_rate)
        env_var.add_base(base)
    
    print(f"Creating {len(area_data)} areas...")
    

    for i in range(len(area_data)):
        lat = area_data[i].get("latitude")
        lon = area_data[i].get("longitude")
        order_rate = area_data[i].get("order_rate")
        min_order_rate = area_data[i].get("min_order_rate", 0)
        max_order_rate = area_data[i].get("max_order_rate", 50)
        std_order_rate = area_data[i].get("std_order_rate", 1)
        mean_order_rate = area_data[i].get("mean_order_rate", 10)
        
        area_node = get_nearest_node(lat, lon)
        area = Area(env=env, env_var=env_var, G=G, node_id=area_node, order_rate=order_rate,
                   min_order_rate=min_order_rate, max_order_rate=max_order_rate, std_order_rate=std_order_rate,
                   mean_order_rate=mean_order_rate)
        env_var.add_area(area)
    

    order_system = Order_system(G=G, env=env, env_var=env_var, order_queue=[])
    env_var.set_order_system(order_system)
    

    debug_node_types()
    env.process(init_simulation(env_var=env_var))
    


    mqtt_client = DirectMQTTClient(broker, mqtt_port, simulation_object=env_var)
    mqtt_client.connect()
    mqtt_client.subscribe(topic_taxi_assignmet, handle_taxi_assignment)



    print("Starting simulation...")
    start_time = time.time()
    

    simulation_duration = 1000
    

    progress_interval = simulation_duration / 10
    next_progress = progress_interval
    
    def report_progress():
        while env.now < simulation_duration:
            real_elapsed = time.time() - start_time
            print(f"Simulation time: {env.now:.1f}/{simulation_duration} ({env.now/simulation_duration*100:.1f}%) - Real time: {real_elapsed:.1f}s")
            yield env.timeout(progress_interval)
    
    env.process(report_progress())
    

    env.run(until=simulation_duration)
    

    elapsed_time = time.time() - start_time
    print(f"\nSimulation completed!")
    print(f"Simulated time: {simulation_duration} units")
    print(f"Real time elapsed: {elapsed_time:.2f} seconds")
    print(f"Speed ratio: {simulation_duration/elapsed_time:.2f}x real-time")
    print(f"Number of taxis: {JUMLAH_TAXI}")


