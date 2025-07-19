import requests
import logging
import math

logger = logging.getLogger(__name__)

api_order_rate_simulation_url = "http://order-rate-backend-simulation-60-bases:5022"
OSRM_URL = "http://osrm:5003"

MAX_COORD = 1000

def get_osrm_matrix(coords, osrm_url=OSRM_URL, sources=None, destinations=None):
    try:
        if sources is None:
            sources = list(range(len(coords)))
        if destinations is None:
            destinations = list(range(len(coords)))

        total_sources = len(sources)
        total_destinations = len(destinations)

        durations = [[None] * total_destinations for _ in range(total_sources)]
        distances = [[None] * total_destinations for _ in range(total_sources)]

        logger.info(f"Total sources: {total_sources}, destinations: {total_destinations}")

        for src_start in range(0, total_sources, MAX_COORD):
            src_end = min(src_start + MAX_COORD, total_sources)
            src_batch = sources[src_start:src_end]

            for dst_start in range(0, total_destinations, MAX_COORD):
                dst_end = min(dst_start + MAX_COORD, total_destinations)
                dst_batch = destinations[dst_start:dst_end]

                logger.info(f"Requesting OSRM batch: sources {src_start}-{src_end}, destinations {dst_start}-{dst_end}")

                params = {
                    "sources": ";".join(map(str, src_batch)),
                    "destinations": ";".join(map(str, dst_batch)),
                    "annotations": "duration,distance"
                }

                coord_str = ";".join([f"{lon},{lat}" for lon, lat in coords])

                resp = requests.get(
                    f"{osrm_url}/table/v1/driving/{coord_str}",
                    params=params,
                    timeout=300
                )

                if not resp.ok:
                    logger.error(f"Batch request failed: {resp.text}")
                    return None

                json_data = resp.json()
                dur_matrix = json_data.get("durations", [])
                dist_matrix = json_data.get("distances", [])

                for i, src_global_idx in enumerate(src_batch):
                    for j, dst_global_idx in enumerate(dst_batch):

                        durations[src_start + i][dst_start + j] = dur_matrix[i][j]
                        distances[src_start + i][dst_start + j] = dist_matrix[i][j]

        logger.info("Successfully fetched OSRM matrix in batches")
        return {"durations": durations, "distances": distances}

    except Exception as e:
        logger.error(f"Exception in get_osrm_matrix_chunked: {e}")
        return None

def get_cumulative_order_rate_matrix(source_coords, destination_coords):
    """
    Get cumulative order rate matrix from the order rate simulation API.
    
    Parameters:
        source_coords: List of (lat, lon) tuples for source points
        destination_coords: List of (lat, lon) tuples for destination points
        
    Returns:
        2D list where matrix[i][j] is cumulative order rate from source_coords[i] to destination_coords[j]
    """
    try:
        resp = requests.post(
            f"{api_order_rate_simulation_url}/get_cumulative_order_rate_matrix",
            json={
                "source_coords": source_coords,
                "destination_coords": destination_coords
            },
            timeout=3000  
        )
        
        if resp.ok:
            result = resp.json()
            return result.get("cumulative_order_rate_matrix")
        else:
            logger.error("Error getting cumulative order rate matrix: %s", resp.text)
            return None
    except Exception as e:
        logger.error("Exception getting cumulative order rate matrix: %s", e)
        return None

def get_vector_base_order_rate(base_ids):
    """
    Get base order rates for multiple base IDs.
    
    Parameters:
        base_ids: List of base IDs
        
    Returns:
        List of base order rates corresponding to the input base IDs
    """
    try:
        resp = requests.post(
            f"{api_order_rate_simulation_url}/get_vector_base_order_rate",
            json={"base_ids": base_ids},
            timeout=10
        )
        
        if resp.ok:
            result = resp.json()
            print(f"base_order_rates: {result.get('base_order_rates')}")
            return result.get("base_order_rates")
        else:
            logger.error("Error getting vector base order rate: %s", resp.text)
            return None
    except Exception as e:
        logger.error("Exception getting vector base order rate: %s", e)
        return None
