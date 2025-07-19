import osmnx as ox
import networkx as nx
from shapely.geometry import LineString, Point
import time
import json
import paho.mqtt.client as mqtt
import numpy as np
import random
import threading
import polyline
import os
import pickle

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(BASE_DIR, "bandung_drive_osm.pkl"), "rb") as f:
    G = pickle.load(f)


def get_node_lat_lon(node_id, G=G):

    d = dict(list(G.nodes(data=True)))
    node_data = d[node_id]
    return (node_data["y"], node_data["x"])



def get_route(init_node, dest_node, G=G):
    """
    function yang melakukan routing dari init_node ke dest_node

    function ini merupakan pengganti route dari BE dan route dari myBlueBird(pokonya routing itu dari luar simulasi) -> simulasimah hanya nerima route dan mensimulasikannya

    args: 
    init_node -> id node awal
    dest_node -> id node tujuan
    G -> graph (G yang harus sudah ada kolom duration pada G.edges(keys=True, data=True))

    return: route yang berupa array of node_id
    """
    route = nx.shortest_path(G, init_node, dest_node, weight='duration')
    return route

def get_nearest_node(lat, lon, G=G):
    """
    mengambil node terdekat dari lat dan lon tertentu

    param:
    G -> graph (G yang harus sudah ada kolom duration pada G.edges(keys=True, data=True))
    lat -> latitude
    lon -> longitude
    """
    return str(ox.distance.nearest_nodes(G, float(lon), float(lat)))


def find_edges(u, v, G=G):
    """
    menerima:
    u -> id node asal
    v -> id node tujuan
    G -> graph (G yang harus sudah ada kolom duration pada G.edges(keys=True, data=True))

    return: edges yang memiliki titik asal node dengan id u dan titik tujuan dengan node v
    """
    edges_numpy = np.array(list(G.edges(keys=True, data=True)))
    mask = (edges_numpy[:, 0] == u) & (edges_numpy[:, 1] == v)
    filtered = edges_numpy[mask]
    return filtered[0]


def get_route_by_lat_lon(coordAwal, coordAkhir, G=G):
    """
    function yang menerima coordAwal dan coordAkhir, serta mengembalikan rute

    param:
    G -> graph
    coordAwal -> (latAwal, lonAwal)
    coordAkhir -> (latAkhir, lonAkhir)

    return route
    """
    latAwal, lonAwal = coordAwal
    latAkhir, lonAkhir = coordAkhir
    origin = ox.distance.nearest_nodes(G, lonAwal, latAwal)
    destination = ox.distance.nearest_nodes(G, lonAkhir, latAkhir)
    route = get_route(init_node=origin, dest_node=destination)
    return route