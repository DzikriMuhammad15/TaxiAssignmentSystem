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

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load the graph
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
graph_path = os.path.join(BASE_DIR, "bandung_drive_osm.pkl")

try:
    with open(graph_path, "rb") as f:
        G = pickle.load(f)
    logger.info(f"Graph loaded successfully with {len(G.nodes)} nodes and {len(G.edges)} edges")
except FileNotFoundError:
    logger.error(f"Graph file not found at {graph_path}")
    G = None
except Exception as e:
    logger.error(f"Error loading graph: {str(e)}")
    G = None

@lru_cache(maxsize=512)
def get_node_lat_lon(node_id, G=G):
    
    try:
        if G is None or node_id not in G.nodes:
            return None
        node_data = G.nodes[node_id]
        if 'y' not in node_data or 'x' not in node_data:
            return None
        return (node_data["y"], node_data["x"])
    except Exception as e:
        logger.error(f"Error getting coordinates for node {node_id}: {str(e)}")
        return None

@lru_cache(maxsize=1024)
def get_route(init_node, dest_node, G=G):
    
    try:
        if G is None:
            return []
        if init_node == dest_node:
            return [init_node]
        if init_node not in G.nodes or dest_node not in G.nodes:
            return []
        route = nx.shortest_path(G, init_node, dest_node, weight='length')
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
        if G is None:
            return None
        if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
            return None
        return ox.distance.nearest_nodes(G, float(lon), float(lat))
    except Exception as e:
        logger.error(f"Error finding nearest node for ({lat}, {lon}): {str(e)}")
        return None

def find_edges(u, v, G=G):
    
    try:
        if G is None or not G.has_edge(u, v):
            return None
        edge_data = G[u][v]
        if isinstance(edge_data, dict):
            if 0 in edge_data:
                return edge_data[0]
            else:
                return list(edge_data.values())[0]
        return edge_data
    except Exception as e:
        logger.error(f"Error finding edges between {u} and {v}: {str(e)}")
        return None

@lru_cache(maxsize=512)
def get_route_by_lat_lon_with_fallback(coordAwal, coordAkhir, G=G):
    
    try:
        if G is None:
            return [], None, None
            
        latAwal, lonAwal = coordAwal
        latAkhir, lonAkhir = coordAkhir
        
        if not all(-90 <= lat <= 90 for lat in [latAwal, latAkhir]):
            return [], None, None
        if not all(-180 <= lon <= 180 for lon in [lonAwal, lonAkhir]):
            return [], None, None
        
        origin = get_nearest_node(latAwal, lonAwal, G)
        destination = get_nearest_node(latAkhir, lonAkhir, G)
        
        if origin is None or destination is None:
            return [], origin, destination
        
        # Try to find normal route
        route = get_route(init_node=origin, dest_node=destination, G=G)
        
        if route:
            logger.info(f"Found route with {len(route)} nodes")
            return route, origin, destination
        else:
            # Fallback: return route with only destination node
            logger.warning(f"No route found, using fallback with destination node {destination}")
            return [destination], origin, destination
            
    except Exception as e:
        logger.error(f"Error calculating route by coordinates: {str(e)}")
        return [], None, None

# Keep the original function for backward compatibility
@lru_cache(maxsize=512)
def get_route_by_lat_lon(coordAwal, coordAkhir, G=G):
    
    route, _, _ = get_route_by_lat_lon_with_fallback(coordAwal, coordAkhir, G)
    return route

# Clear cache periodically
def clear_cache_periodically():
    
    while True:
        time.sleep(3600)
        try:
            get_node_lat_lon.cache_clear()
            get_route.cache_clear()
            get_nearest_node.cache_clear()
            get_route_by_lat_lon.cache_clear()
            get_route_by_lat_lon_with_fallback.cache_clear()
            logger.info("Cleared function caches")
        except Exception as e:
            logger.error(f"Error clearing caches: {str(e)}")

if G is not None:
    cache_thread = threading.Thread(target=clear_cache_periodically, daemon=True, name="cache_cleaner")
    cache_thread.start()
