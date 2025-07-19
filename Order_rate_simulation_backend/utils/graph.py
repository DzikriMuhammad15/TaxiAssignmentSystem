import osmnx as ox
import networkx as nx
from shapely.geometry import LineString, Point
import time
import json
import numpy as np
import random
import threading
import polyline
import os
import logging
from functools import lru_cache
import pickle


logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(BASE_DIR, "bandung_drive_osm.pkl"), "rb") as f:
    G = pickle.load(f)


@lru_cache(maxsize=512)
def get_node_lat_lon(node_id, G=G):
    
    try:
        node_data = G.nodes[node_id]
        return (node_data["y"], node_data["x"])
    except KeyError:
        logger.error(f"Node {node_id} not found in graph")
        return None

@lru_cache(maxsize=1024)
def get_route(init_node, dest_node, G=G):
    
    try:
        if init_node == dest_node:
            return [init_node]
            
        route = nx.shortest_path(G, init_node, dest_node, weight='duration')
        return route
        
    except nx.NetworkXNoPath:
        logger.warning(f"No path found from {init_node} to {dest_node}")
        return []
    except Exception as e:
        logger.error(f"Error finding route: {str(e)}")
        return []

@lru_cache(maxsize=2048)
def get_nearest_node(lat, lon, G=G):
    
    try:
        return ox.distance.nearest_nodes(G, float(lon), float(lat))
    except Exception as e:
        logger.error(f"Error finding nearest node for ({lat}, {lon}): {str(e)}")
        return None

def find_edges(u, v, G=G):
    
    try:
        if G.has_edge(u, v):
            return G[u][v]
        else:
            logger.warning(f"No edge found between {u} and {v}")
            return None
    except Exception as e:
        logger.error(f"Error finding edges: {str(e)}")
        return None

@lru_cache(maxsize=512)
def get_route_by_lat_lon(coordAwal, coordAkhir, G=G):
    
    try:
        latAwal, lonAwal = coordAwal
        latAkhir, lonAkhir = coordAkhir
        
        origin = get_nearest_node(latAwal, lonAwal, G)
        destination = get_nearest_node(latAkhir, lonAkhir, G)
        
        if origin is None or destination is None:
            logger.error("Could not find nearest nodes for coordinates")
            return []
            
        route = get_route(init_node=origin, dest_node=destination, G=G)
        return route
        
    except Exception as e:
        logger.error(f"Error calculating route by coordinates: {str(e)}")
        return []


def clear_cache_periodically():
    
    while True:
        time.sleep(3600)
        try:
            get_node_lat_lon.cache_clear()
            get_route.cache_clear()
            get_nearest_node.cache_clear()
            get_route_by_lat_lon.cache_clear()
            logger.info("Cleared function caches")
        except Exception as e:
            logger.error(f"Error clearing caches: {str(e)}")


cache_thread = threading.Thread(target=clear_cache_periodically, daemon=True, name="cache_cleaner")
cache_thread.start()
