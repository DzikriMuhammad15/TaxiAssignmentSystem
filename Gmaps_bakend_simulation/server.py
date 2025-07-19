import osmnx as ox
import networkx as nx
from shapely.geometry import LineString, Point
import time
import json
import numpy as np
import random
import threading
import polyline
from utils.graph import G, get_node_lat_lon, get_route, get_nearest_node, find_edges, get_route_by_lat_lon, get_route_by_lat_lon_with_fallback
from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import zlib
import base64
import logging
import traceback


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_route_polyline(coordAwal, coordAkhir, G=G):
    
    try:
        if G is None:
            logger.error("Graph not loaded")
            return polyline.encode([]), []
            

        route, origin_node, dest_node = get_route_by_lat_lon_with_fallback(
            coordAwal=coordAwal, coordAkhir=coordAkhir, G=G
        )
        
        if not route:
            logger.error("No route found and no fallback available")
            return polyline.encode([]), []
        

        is_fallback = len(route) == 1 and route[0] == dest_node
        
        if is_fallback:
            logger.info(f"Using fallback route with destination node {dest_node}")
        else:
            logger.info(f"Found normal route with {len(route)} nodes")
        

        poly = []
        for node in route:
            try:
                if node not in G.nodes:
                    logger.warning(f"Node {node} not found in graph")
                    continue
                    
                node_data = G.nodes[node]
                if 'y' not in node_data or 'x' not in node_data:
                    logger.warning(f"Node {node} missing coordinates")
                    continue
                    
                lat, lon = node_data['y'], node_data['x']
                if -90 <= lat <= 90 and -180 <= lon <= 180:
                    poly.append((lat, lon))
                else:
                    logger.warning(f"Invalid coordinates for node {node}: ({lat}, {lon})")
                    
            except Exception as e:
                logger.error(f"Error processing node {node}: {str(e)}")
                continue
        
        if not poly:
            logger.error("No valid coordinates extracted from route")

            if dest_node is not None:
                dest_coords = get_node_lat_lon(dest_node, G)
                if dest_coords:
                    logger.info("Using destination coordinates as last resort")
                    poly = [dest_coords]
                    route = [dest_node]
        
        if not poly:
            logger.error("Complete failure - no coordinates available")
            return polyline.encode([]), []
            
        logger.info(f"Successfully created polyline with {len(poly)} points (fallback: {is_fallback})")
        return polyline.encode(poly), route
        
    except Exception as e:
        logger.error(f"Error in get_route_polyline: {str(e)}")
        logger.error(traceback.format_exc())
        return polyline.encode([]), []

def get_travel_duration(coordAwal, coordAkhir, G=G):
    
    try:
        if G is None:
            return 0
            
        route, origin_node, dest_node = get_route_by_lat_lon_with_fallback(
            coordAwal=coordAwal, coordAkhir=coordAkhir, G=G
        )
        
        if not route:
            return 0
            

        if len(route) == 1:
            logger.info("Fallback route - returning 0 duration")
            return 0
            

        if origin_node and dest_node:
            estimated_duration = nx.shortest_path_length(G, origin_node, dest_node, weight='length')
            return estimated_duration
        
        return 0
        
    except Exception as e:
        logger.error(f"Error calculating travel duration: {str(e)}")
        return 0

def get_travel_distance(coordAwal, coordAkhir, G=G):
    
    try:
        if G is None:
            return 0
            
        route, origin_node, dest_node = get_route_by_lat_lon_with_fallback(
            coordAwal=coordAwal, coordAkhir=coordAkhir, G=G
        )
        
        if not route:
            return 0
            

        if len(route) == 1:
            logger.info("Fallback route - returning 0 distance")
            return 0
            

        if origin_node and dest_node:
            estimated_length = nx.shortest_path_length(G, origin_node, dest_node, weight='length')
            return estimated_length
        
        return 0
        
    except Exception as e:
        logger.error(f"Error calculating travel distance: {str(e)}")
        return 0

def encode_array(data_array):
    
    try:
        if not data_array:
            return ""
        json_str = json.dumps(data_array)
        compressed = zlib.compress(json_str.encode('utf-8'))
        base64_str = base64.b64encode(compressed).decode('utf-8')
        return base64_str
    except Exception as e:
        logger.error(f"Error encoding array: {str(e)}")
        return ""

app = Flask(__name__)
CORS(app)

@app.route("/health", methods=["GET"])
def health():
    
    try:
        if G is None:
            return jsonify(status="fail", reason="Graph not loaded"), 500
        return jsonify(status="ok", graph_nodes=len(G.nodes), graph_edges=len(G.edges)), 200
    except Exception as e:
        return jsonify(status="fail", reason=str(e)), 500

@app.route('/route_polyline', methods=['POST'])
def route_polyline():
    
    try:
        if G is None:
            return jsonify({"error": "Graph data not available"}), 503
        
        data = request.get_json()
        if not data or 'coordAwal' not in data or 'coordAkhir' not in data:
            return jsonify({"error": "Missing coordAwal or coordAkhir"}), 400
        
        try:
            coord_awal = tuple(data['coordAwal'])
            coord_akhir = tuple(data['coordAkhir'])
        except (KeyError, TypeError, ValueError) as e:
            return jsonify({"error": f"Invalid coordinate format: {str(e)}"}), 400
        

        try:
            lat_awal, lon_awal = coord_awal
            lat_akhir, lon_akhir = coord_akhir
            if not (-90 <= lat_awal <= 90 and -90 <= lat_akhir <= 90):
                return jsonify({"error": "Invalid latitude values"}), 400
            if not (-180 <= lon_awal <= 180 and -180 <= lon_akhir <= 180):
                return jsonify({"error": "Invalid longitude values"}), 400
        except:
            return jsonify({"error": "Invalid coordinate format"}), 400
        

        if coord_awal == coord_akhir:
            return jsonify({
                "polyline": polyline.encode([coord_awal]), 
                "encoded_route_node_id": encode_array([]),
                "is_fallback": False
            })
        

        encoded, route = get_route_polyline(coord_awal, coord_akhir, G)
        

        if not encoded:

            logger.error("Fallback mechanism failed")
            return jsonify({"error": "Unable to generate route"}), 500
        

        is_fallback = len(route) == 1
        
        encoded_route = encode_array(route)
        
        response = {
            "polyline": encoded, 
            "encoded_route_node_id": encoded_route,
            "is_fallback": is_fallback,
            "route_length": len(route)
        }
        
        if is_fallback:
            logger.info("Returned fallback route")
        else:
            logger.info(f"Returned normal route with {len(route)} nodes")
            
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"Error in route_polyline: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500

@app.route('/travel_duration', methods=['POST'])
def travel_duration():
    
    try:
        if G is None:
            return jsonify({"error": "Graph data not available"}), 503
        data = request.get_json()
        if not data or 'coordAwal' not in data or 'coordAkhir' not in data:
            return jsonify({"error": "Missing coordAwal or coordAkhir"}), 400
        coord_awal = tuple(data['coordAwal'])
        coord_akhir = tuple(data['coordAkhir'])
        duration = get_travel_duration(coord_awal, coord_akhir, G)
        return jsonify({"duration": duration})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/travel_distance', methods=['POST'])
def travel_distance():
    
    try:
        if G is None:
            return jsonify({"error": "Graph data not available"}), 503
        data = request.get_json()
        if not data or 'coordAwal' not in data or 'coordAkhir' not in data:
            return jsonify({"error": "Missing coordAwal or coordAkhir"}), 400
        coord_awal = tuple(data['coordAwal'])
        coord_akhir = tuple(data['coordAkhir'])
        distance = get_travel_distance(coord_awal, coord_akhir, G)
        return jsonify({"distance": distance})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    if G is None:
        logger.error("Cannot start server: Graph not loaded")
        exit(1)
    logger.info(f"Starting server with graph: {len(G.nodes)} nodes, {len(G.edges)} edges")
    app.run(host='0.0.0.0', port=5001, debug=True, use_reloader=False)
