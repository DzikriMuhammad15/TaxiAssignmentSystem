import requests
import logging

logger = logging.getLogger(__name__)

def get_travel_duration(coordAwal, coordAkhir, api_gmaps_simulation_url):
    try:
        if not coordAwal or not coordAkhir or len(coordAwal) != 2 or len(coordAkhir) != 2:
            return None
        
        resp = requests.post(
            f"{api_gmaps_simulation_url}/travel_duration",
            json={"coordAwal": list(coordAwal), "coordAkhir": list(coordAkhir)},
            timeout=20,
            headers={'Content-Type': 'application/json'}
        )
        
        if resp.ok:
            data = resp.json()
            return data.get("duration")
        else:
            return None
            
    except requests.exceptions.Timeout:
        return None
    except Exception as e:
        return None

def get_route_polyline(coordAwal, coordAkhir, api_gmaps_simulation_url):
    try:
        if not coordAwal or not coordAkhir or len(coordAwal) != 2 or len(coordAkhir) != 2:
            return None, None
        
        resp = requests.post(
            f"{api_gmaps_simulation_url}/route_polyline",
            json={"coordAwal": list(coordAwal), "coordAkhir": list(coordAkhir)},
            timeout=30,
            headers={'Content-Type': 'application/json'}
        )
        
        if resp.ok:
            data = resp.json()
            polyline_data = data.get("polyline")
            encoded_route_node_id = data.get("encoded_route_node_id")
            return polyline_data, encoded_route_node_id
        else:
            return None, None
            
    except requests.exceptions.Timeout:
        return None, None
    except Exception as e:
        return None, None

def get_travel_distance(coordAwal, coordAkhir, api_gmaps_simulation_url):
    try:
        if not coordAwal or not coordAkhir or len(coordAwal) != 2 or len(coordAkhir) != 2:
            return None
        
        resp = requests.post(
            f"{api_gmaps_simulation_url}/travel_distance",
            json={"coordAwal": list(coordAwal), "coordAkhir": list(coordAkhir)},
            timeout=20,
            headers={'Content-Type': 'application/json'}
        )
        
        if resp.ok:
            data = resp.json()
            return data.get("distance")
        else:
            return None
            
    except requests.exceptions.Timeout:
        return None
    except Exception as e:
        return None

def get_cumulative_order_rate(coordAwal, coordAkhir, api_order_rate_simulation_url):
    try:
        resp = requests.post(
            f"{api_order_rate_simulation_url}/get_cumulative_order_rate",
            json={"coordAwal": coordAwal, "coordAkhir": coordAkhir},
            timeout=10 
        )
        if resp.ok:
            cummulative_order_rate = resp.json().get("cumulative_order_rate")
            return cummulative_order_rate if cummulative_order_rate is not None else 0
        else:
            return 0
    except requests.exceptions.Timeout:
        return 0
    except Exception as e:
        return 0

def get_base_order_rate(base_id, api_order_rate_simulation_url):
    try:
        resp = requests.post(
            f"{api_order_rate_simulation_url}/get_base_order_rate",
            json={"base_id": str(base_id)},
            timeout=10  
        )
        if resp.ok:
            base_order_rate = resp.json().get("base_order_rate")
            return base_order_rate if base_order_rate is not None else 0
        else:
            return 0
    except requests.exceptions.Timeout:
        return 0
    except Exception as e:
        return 0
