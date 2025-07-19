import random
import copy
from .matrix_api_client import get_osrm_matrix, get_cumulative_order_rate_matrix, get_vector_base_order_rate
import requests
import math
import logging
import time
from collections import defaultdict
from functools import lru_cache

logger = logging.getLogger(__name__)



def get_route_polyline(coordAwal, coordAkhir):
    """
    coordAwal -> (lat, lon)
    coordAkhir -> (lat, lon)
    """
    try:
        resp = requests.post(
            f"{api_gmaps_simulation_url}/route_polyline",
            json={"coordAwal": coordAwal, "coordAkhir": coordAkhir},
            timeout=5
        )
        if resp.ok:
            polyline = resp.json().get("polyline")
            return polyline
        else:
            logger.error("Error getting route polyline: %s", resp.text)
            return None
    except Exception as e:
        logger.error("Exception getting route polyline: %s", e)
        return None

def get_taxi_map(taxi_data):
    """
    mapping dari index solusi ke taxi id
    """
    taxi_kosong = {k: v for k, v in taxi_data.items() if v.get("taxi_state") == "kosong"}
    map_list = [None] * len(list(taxi_kosong.keys()))
    for i in range(len(list(taxi_kosong.keys()))):
        map_list[i] = list(taxi_kosong.keys())[i]
    return map_list

def get_base_map(requests):
    """
    memetakan request ke base_id
    mengembalikan: 
    base_map: array berisi base_id secara unik
    request_to_base_map: array berisi mapping dari requests ke base_id
    base_request_counts: array berisi banyaknya request dari setiap base_id
    """

    base_requests = defaultdict(int)
    for base_id in requests:
        base_requests[base_id] += 1
    

    unique_bases = list(base_requests.keys())
    base_map = unique_bases
    

    request_to_base_map = []
    base_request_counts = []
    
    for base_id in requests:
        base_index = unique_bases.index(base_id)
        request_to_base_map.append(base_index)
    
    for base_id in unique_bases:
        base_request_counts.append(base_requests[base_id])
    
    return base_map, request_to_base_map, base_request_counts

def num_taxi_kosong(taxi_data):
    """
    menerima taxi data dan mengembalikan banyaknya taxi yang kosong
    """
    taxi_kosong = {k: v for k, v in taxi_data.items() if v.get("taxi_state") == "kosong"}
    return len(taxi_kosong.keys())

class FIRCache:
    def __init__(self):
        self.cache = {}
        self.hits = 0
        self.misses = 0
    
    def get_cache_key(self, taxi_idx, base_idx, duration, cumulative_order_rate, base_order_rate):
        """membuat key untuk cache"""
        return (taxi_idx, base_idx, round(duration, 2), round(cumulative_order_rate, 4), round(base_order_rate, 2))
    
    def get_fir(self, taxi_idx, base_idx, duration, cumulative_order_rate, base_order_rate, precObject):
        """hitung fir (kalau ada di cache, gunakan cache)"""
        cache_key = self.get_cache_key(taxi_idx, base_idx, duration, cumulative_order_rate, base_order_rate)
        
        if cache_key in self.cache:
            self.hits += 1
            return self.cache[cache_key]
    
        alpha = precObject.alpha
        beta = precObject.beta
        gamma = precObject.gamma
        
        d_hat = 0 if(duration == 0) else max((duration - precObject.min_duration), duration) / max((precObject.max_duration - precObject.min_duration), duration)
        cumulative_hat = 0 if(cumulative_order_rate == 0) else max((cumulative_order_rate - precObject.min_cumulative_order_rate), cumulative_order_rate) / max((precObject.max_cumulative_order_rate - precObject.min_cumulative_order_rate), cumulative_order_rate)
        base_order_rate_hat = 0 if(base_order_rate == 0) else max((base_order_rate - precObject.min_base_order_rate), base_order_rate) / max((precObject.max_base_order_rate - precObject.min_base_order_rate), base_order_rate)
        
        fir = (alpha * (1 - d_hat)) + (beta * (1 - cumulative_hat)) + (gamma * base_order_rate_hat)
        

        self.cache[cache_key] = fir
        self.misses += 1
        
        return fir
    
    def clear(self):
        """Clear cache"""
        self.cache.clear()
        self.hits = 0
        self.misses = 0

def fitness_function_optimized(taxi_assignments_configuration, precObject):
    """
    menghitung fitness function konfigurasi dengan mekanisme cache
    """
    objective = 0
    

    base_assignments = defaultdict(list)
    for i, assigned_base_request in enumerate(taxi_assignments_configuration):
        if assigned_base_request is not None:

            actual_base_idx = precObject.request_to_base_map[assigned_base_request]
            base_assignments[actual_base_idx].append(i)
    

    for base_idx, taxi_indices in base_assignments.items():

        base_order_rate = precObject.base_order_rates[base_idx]
        
        for taxi_idx in taxi_indices:

            duration_seconds = precObject.duration_matrix[taxi_idx][base_idx]
            cumulative_order_rate = precObject.cumulative_order_rate_matrix[taxi_idx][base_idx]
            

            fir = precObject.fir_cache.get_fir(
                taxi_idx, base_idx, duration_seconds, 
                cumulative_order_rate, base_order_rate, precObject
            )
            
            objective += fir
    
    return objective

def fitness_function(taxi_assignments_configuration, precObject):
     return fitness_function_optimized(taxi_assignments_configuration, precObject)


def estimated_battery_after_trip(current_battery, distance, precObject):
    alpha_d = precObject.alpha_d
    alpha_t = precObject.alpha_t
    battery_consumption = distance * alpha_d
    return current_battery - battery_consumption

def constraint_satisfied(taxi_assignments_configuration, precObject):
    """
    Check constraint
    """
    for i in range(len(taxi_assignments_configuration)):
        assigned_base_request = taxi_assignments_configuration[i]
        
        if assigned_base_request is not None:

            taxi_id = precObject.taxi_map[i]
            taxi_battery = precObject.taxi_data[taxi_id]["battery"]
            

            actual_base_idx = precObject.request_to_base_map[assigned_base_request]
            distance = precObject.distance_matrix[i][actual_base_idx]
            

            estimated_battery = estimated_battery_after_trip(taxi_battery, distance, precObject=precObject)
            
            if estimated_battery < precObject.battery_treshold:
                return False
    
    return True

def generate_random_solution(num_taxi, num_requests):
    solution = [None] * num_taxi
    

    available_requests = list(range(num_requests))
    

    for i in range(min(num_taxi, num_requests)):
        if available_requests:
            request_index = random.choice(available_requests)
            solution[i] = request_index
            available_requests.remove(request_index)
    
    return solution

def generate_greedy_solution(precObject):
    """
    Membuat a greedy solution
    """
    num_taxi = len(precObject.taxi_map)
    
    num_requests = len(precObject.request_to_base_map)
    available_requests = list(range(num_requests))
    
    solution = [None] * num_taxi
    

    for i in range(num_taxi):
        best_request = None
        best_fitness = float('-inf')
        
        for request_idx in available_requests:

            taxi_id = precObject.taxi_map[i]
            taxi_battery = precObject.taxi_data[taxi_id]["battery"]
            
            actual_base_idx = precObject.request_to_base_map[request_idx]
            distance = precObject.distance_matrix[i][actual_base_idx]
            base_order_rate = precObject.base_order_rates[actual_base_idx]
            duration_seconds = precObject.duration_matrix[i][actual_base_idx]
            cumulative_order_rate = precObject.cumulative_order_rate_matrix[i][actual_base_idx]
            

            estimated_battery = estimated_battery_after_trip(taxi_battery, distance, precObject=precObject)
            if estimated_battery < precObject.battery_treshold:
                continue 
            

            fir = precObject.fir_cache.get_fir(
                i, request_idx if not hasattr(precObject, 'use_optimized_fitness') else actual_base_idx,
                duration_seconds, cumulative_order_rate, base_order_rate, precObject
            )
            
            if fir > best_fitness:
                best_fitness = fir
                best_request = request_idx
        
        if best_request is not None:
            solution[i] = best_request
            available_requests.remove(best_request)
    
    return solution

def path_relinking(solution1, solution2, precObject, c):
    """
    mengembalikan c solusi terbaik.
    
    Args:
    solution1 (list): Solusi awal.
    solution2 (list): Solusi tujuan.
    precObject (obj): Objek yang berisi matriks dan cache untuk perhitungan fitness.
    c (int): Jumlah solusi terbaik yang ingin dikembalikan.

    Returns:
    list: c solusi terbaik (list of list).
    """

    path = []
    current = solution1.copy()
    

    differences = [i for i in range(len(solution1)) if solution1[i] != solution2[i]]
    

    for pos in differences:
        current[pos] = solution2[pos]
        if constraint_satisfied(current, precObject):
            score = fitness_function(current, precObject)
            path.append((current.copy(), score))
    

    path.sort(key=lambda x: x[1])
    
    if len(path) > c:
        best_solutions = [sol for sol, _ in path[:c]]
        
        return best_solutions
    elif len(path) <= 0:
        return [solution1, solution2]
    else:
        return [sol for sol, _ in path[:len(path)]]


def get_duplicate_element(individual):
    seen = set()
    duplicates = set()
    for item in individual:
        if item is not None:
            if item in seen:
                duplicates.add(item)
            else:
                seen.add(item)
    return list(duplicates)

def get_unassigned_request(parent, child):
    not_assigned = []
    for i in range(len(parent)):
        if(parent[i] not in child):
            not_assigned.append(parent[i])
    return not_assigned

def ejection_chain(solution, precObject, max_chain_length=3):
    """
    mengembalikan solusi terbaik dari proses eksplorasi.
    Jika tidak ada perbaikan, mengembalikan solusi awal.

    Args:
    solution (list): Solusi awal.
    precObject (obj): Objek berisi constraint dan matriks evaluasi.
    max_chain_length (int): Panjang maksimum rantai ejection.

    Returns:
    list: Solusi terbaik hasil ejection chain, atau solusi awal jika tidak ada perbaikan.
    """

    best_solution = solution.copy()
    best_fitness = fitness_function(solution, precObject)

    num_taxis = len(solution)

    for start_taxi in range(len(solution)):
        if solution[start_taxi] is None:
            continue

        for chain_length in range(2, min(max_chain_length + 1, len(solution))):
            chain_solution = solution.copy()
            visited_taxis = set()
            current_taxi = start_taxi
            current_request = chain_solution[current_taxi]

            for step in range(chain_length):
                
                available_taxis = [t for t in range(num_taxis) if t != current_taxi and t not in visited_taxis and chain_solution[t] is not None]

                if not available_taxis:
                    break

                next_taxi = random.choice(available_taxis)
                visited_taxis.add(current_taxi)

                temp = chain_solution[next_taxi]
                chain_solution[next_taxi] = current_request
                current_request = temp
                current_taxi = next_taxi

            duplicate_chain_sloution = get_duplicate_element(chain_solution)
            unassigned_chain_solution = get_unassigned_request(solution, chain_solution)
            for i in range(len(duplicate_chain_sloution)):
                duplicate_element = duplicate_chain_sloution[i]
                duplicate_idx = chain_solution.index(duplicate_element)
                if(len(unassigned_chain_solution) > 0):
                    chain_solution[duplicate_idx] = unassigned_chain_solution[0]
                    unassigned_chain_solution.remove(unassigned_chain_solution[0])
                else:
                    chain_solution[duplicate_idx] = None
            for j in range(len(unassigned_chain_solution)):
                unassigned_element = unassigned_chain_solution[j]
                none_idx = chain_solution.index(None)
                chain_solution[none_idx] = unassigned_element

            if constraint_satisfied(chain_solution, precObject):
                chain_fitness = fitness_function(chain_solution, precObject)

                if chain_fitness > best_fitness:
                    best_solution = chain_solution.copy()
                    best_fitness = chain_fitness

    return best_solution



def update_reference_set(reference_set, ec_solution, precObject):
    """
    Update reference_set dengan solusi acak jika lebih baik dari solusi terburuk
    dan tidak ada duplikasi.

    Args:
    reference_set (list of list): Kumpulan solusi yang ada.
    ec_solution (list): Solusi acak yang akan diuji.
    precObject (obj): Objek pendukung untuk perhitungan fitness.

    Returns:
    bool: True jika reference_set diperbarui, False jika tidak.
    """

    if not reference_set:
        return reference_set  


    fitness_list = [fitness_function(sol, precObject) for sol in reference_set]


    worst_idx = fitness_list.index(max(fitness_list))
    worst_fitness = fitness_list[worst_idx]

    random_fitness = fitness_function(ec_solution, precObject)


    if random_fitness < worst_fitness and ec_solution not in reference_set:
        reference_set[worst_idx] = ec_solution.copy()
        return reference_set  

    return reference_set  


class PathRelinkingEjectionChain:
    def __init__(self, battery_treshold=10, reference_set_size=10, alpha_d=0.00024524, alpha_t=0, max_iter_generate=100, alpha=1, beta=1, gamma=1, c=10, max_chain_length=10):
        self.battery_treshold = battery_treshold
        self.reference_set_size = reference_set_size
        self.alpha_d = alpha_d
        self.alpha_t = alpha_t
        self.max_iter_generate = max_iter_generate
        self.alpha = alpha
        self.beta = beta
        self.gamma = gamma
        self.c = c
        self.max_chain_length = max_chain_length
        

        self.taxi_data = None
        self.base_current_state = None
        self.taxi_current_state = None
        self.taxi_map = None
        self.base_map = None
        self.duration_matrix = None
        self.distance_matrix = None
        self.cumulative_order_rate_matrix = None
        self.base_order_rates = None
        

        self.fir_cache = FIRCache()
        self.use_optimized_fitness = True
        self.request_to_base_map = None
        self.base_request_counts = None

    def initialize(self, taxi_data, requests, taxi_current_state, base_current_state):
        try:
            start_time = time.time()
            
            self.taxi_data = taxi_data
            self.base_current_state = base_current_state
            self.taxi_current_state = taxi_current_state
            

            self.fir_cache.clear()
            

            self.taxi_map = get_taxi_map(taxi_data)
            
            self.base_map, self.request_to_base_map, self.base_request_counts = get_base_map(requests)
            logger.info(f"Optimized mapping: {len(requests)} requests -> {len(self.base_map)} unique bases")
            logger.info(f"Base request counts: {dict(zip(self.base_map, self.base_request_counts))}")
        
            if not self.taxi_map or not self.base_map:
                logger.error("Empty taxi or base map")
                return False
            

            logger.info("Pre-calculating matrices for PREC algorithm...")
            

            taxi_coords = []
            for taxi_id in self.taxi_map:
                taxi_state = taxi_data[taxi_id]
                taxi_coords.append((taxi_state["longitude"], taxi_state["latitude"]))
            

            base_coords = []
            for base_id in self.base_map:
                base_state = base_current_state[str(base_id)]
                base_coords.append((base_state["longitude"], base_state["latitude"]))
            

            all_coords = taxi_coords + base_coords
            num_taxis = len(taxi_coords)
            num_bases = len(base_coords)

            logger.info(f"Getting OSRM matrix for {num_taxis} taxis and {num_bases} unique bases...")
            osrm_result = get_osrm_matrix(coords=all_coords, sources=list(range(num_taxis)), destinations=list(range(num_taxis, num_taxis+num_bases)))
            if osrm_result is None:
                logger.error("Failed to get OSRM matrix")
                return False
            
            self.duration_matrix = osrm_result["durations"]
            self.distance_matrix = osrm_result["distances"]


            for i in range(len(self.duration_matrix)):
                for j in range(len(self.duration_matrix[i])):
                    if(self.duration_matrix[i][j] is None):
                        self.duration_matrix[i][j] = 1800

            for m in range(len(self.distance_matrix)):
                for n in range(len(self.distance_matrix[m])):
                    if(self.distance_matrix[m][n] is None):
                        self.distance_matrix[m][n] = 10000

            

            logger.info("Getting cumulative order rate matrix...")
            self.cumulative_order_rate_matrix = get_cumulative_order_rate_matrix(taxi_coords, base_coords)
            if self.cumulative_order_rate_matrix is None:
                logger.error("Failed to get cumulative order rate matrix")
                return False


            for a in range(len(self.cumulative_order_rate_matrix)):
                for b in range(len(self.cumulative_order_rate_matrix[a])):
                    if(self.cumulative_order_rate_matrix[a][b] is None):
                        self.cumulative_order_rate_matrix[a][b] = 1



            logger.info("Adjusting cumulative order rate matrix by duration...")
            for i in range(len(self.cumulative_order_rate_matrix)):
                for j in range(len(self.cumulative_order_rate_matrix[i])):
                    if(self.duration_matrix[i][j] is None):
                        self.duration_matrix[i][j] = 1800
                    duration_hours = self.duration_matrix[i][j] / 3600.0
                    self.cumulative_order_rate_matrix[i][j] *= duration_hours
        

            logger.info("Getting base order rates...")
            self.base_order_rates = get_vector_base_order_rate(self.base_map)
            if self.base_order_rates is None:
                logger.error("Failed to get base order rates")
                return False
            
            for r in range(len(self.base_order_rates)):
                if(self.base_order_rates[r] is None):
                    self.base_order_rates[r] = 1


            flat_duration = [item for row in self.duration_matrix for item in row]
            self.min_duration = min(flat_duration)
            self.max_duration = max(flat_duration)


            flat_cumulative_order_rate = [item for row in self.cumulative_order_rate_matrix for item in row]
            self.min_cumulative_order_rate = min(flat_cumulative_order_rate)
            self.max_cumulative_order_rate = max(flat_cumulative_order_rate)


            self.min_base_order_rate = min(self.base_order_rates)
            self.max_base_order_rate = max(self.base_order_rates)

            initialization_time = time.time() - start_time
            logger.info(f"Matrix pre-calculation completed successfully in {initialization_time:.2f} seconds")
            logger.info(f"Matrix dimensions: {len(self.duration_matrix)}x{len(self.duration_matrix[0])}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error in PREC initialization: {e}")
            return False

    def run(self, num_of_cycle=1, requests=None, taxi_data=None, ec_probe_iteration=5):
        try:
            start_time = time.time()
            best_solution = None
            best_fitness = float('-inf')
            
            reference_set = []
            S = []
            if not all([self.taxi_map, self.base_map, self.duration_matrix, 
                       self.distance_matrix, self.cumulative_order_rate_matrix, 
                       self.base_order_rates]):
                logger.error("PREC not properly initialized")
                return {"configuration": {}, "fitness": -1}
            
            num_taxi = len(self.taxi_map)
            
            num_requests = len(self.request_to_base_map)
            logger.info(f"Running optimized PREC with {num_taxi} taxis, {num_requests} requests, and {len(self.base_map)} unique bases")
            

            

            greedy_solution = generate_greedy_solution(self)
            if constraint_satisfied(greedy_solution, self):
                reference_set.append(greedy_solution)
            

            max_attempts = self.max_iter_generate
            attempts = 0
            
            while len(reference_set) < self.reference_set_size and attempts < max_attempts:
                random_solution = generate_random_solution(num_taxi, num_requests)
                if constraint_satisfied(random_solution, self):
                    reference_set.append(random_solution)
                attempts += 1
            
            if not reference_set:
                logger.warning("No feasible solutions found in reference set")
                return {"configuration": {}, "fitness": -1}
            
            logger.info(f"Initial reference set size: {len(reference_set)}")

            for cycle in range(num_of_cycle):
                cycle_start = time.time()
                logger.info(f"PREC Cycle {cycle + 1}/{num_of_cycle}")
                if len(S) <= 0:
                    print("memulai path relinking loop...")
                    for i in range(len(reference_set)):
                        for j in range(i + 1, len(reference_set)):
                            print("memulai path relinking...")
                            path = path_relinking(reference_set[i], reference_set[j], self, self.c)
                            print(f"selesai path relinking...")
                            S.extend(path)
                    print("selesai path relinking loop")
                random_select_solution = random.choice(S)
                S.remove(random_select_solution)

                print("memulai ejection chain")
                ec_solution = ejection_chain(random_select_solution, self, self.max_chain_length)
                print("selesai ejection chain")


                print("update R")
                reference_set = update_reference_set(reference_set, ec_solution, self)
                print("selesai update R")
                for solution in reference_set:
                    fitness_val = fitness_function(solution, self)
                    if fitness_val > best_fitness:
                        best_fitness = fitness_val
                        best_solution = solution


                cycle_time = time.time() - cycle_start
                logger.info(f"Cycle {cycle + 1} completed")
            

            if best_solution is not None:
                configuration = {}
                for i in range(len(best_solution)):
                    if best_solution[i] is not None:
                        taxi_id = self.taxi_map[i]
                        
                        request_idx = best_solution[i]
                        actual_base_idx = self.request_to_base_map[request_idx]
                        base_id = self.base_map[actual_base_idx]
                        
                        configuration[taxi_id] = base_id
                
                total_time = time.time() - start_time
                
                logger.info(f"PREC completed in {total_time:.2f}s. Final fitness: {best_fitness}")
                logger.info(f"Configuration: {configuration}")
                
                return {"configuration": configuration, "fitness": best_fitness}
            else:
                logger.warning("No solution found")
                return {"configuration": {}, "fitness": -1}
                
        except Exception as e:
            logger.error(f"Error in PREC run: {e}")
            return {"configuration": {}, "fitness": -1}
