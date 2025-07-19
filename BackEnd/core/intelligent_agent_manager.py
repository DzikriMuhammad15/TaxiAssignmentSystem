import threading
import time
import cProfile
import logging
from collections import Counter
from geopy.distance import geodesic
from utils.database import safe_db_operation
from utils.simulation_time import get_current_sim_time
from utils.api_client import get_base_order_rate, get_route_polyline
from utils.profiling import analyze_and_print_profile
from config.settings import *

logger = logging.getLogger(__name__)

class IntelligentAgentManager:
    def __init__(self, intelligent_agent, data_manager, assignment_manager, 
                 taxi_current_state, base_current_state, base_request_data_now,
                 mqtt_handler, connected_clients_map_frontend, socketio,
                 normal_mode_active_event):
        self.intelligent_agent = intelligent_agent
        self.data_manager = data_manager
        self.assignment_manager = assignment_manager
        self.taxi_current_state = taxi_current_state
        self.base_current_state = base_current_state
        self.base_request_data_now = base_request_data_now
        self.mqtt_handler = mqtt_handler
        self.connected_clients_map_frontend = connected_clients_map_frontend
        self.socketio = socketio
        
        self.agent_running = False
        self.agent_thread = None
        self.agent_stop_event = threading.Event()
        self.normal_mode_active_event = normal_mode_active_event

    @staticmethod
    def filter_nearest_taxis(top_order_rates, available_taxi_dict, max_per_base=10, base_current_state=None, taxi_current_state=None):
        used_taxis = set()
        selected_taxis = {}

        if base_current_state is None or taxi_current_state is None:
            logger.error("filter_nearest_taxis requires base_current_state and taxi_current_state")
            return {}

        for base_id in top_order_rates:
            base_coord = (
                base_current_state[str(base_id)]["latitude"],
                base_current_state[str(base_id)]["longitude"]
            )

            distances = []
            for taxi_id, taxi_info in available_taxi_dict.items():
                if taxi_id in used_taxis:
                    continue
                taxi_coord = (
                    taxi_info["latitude"],
                    taxi_info["longitude"]
                )
                distance_km = geodesic(base_coord, taxi_coord).kilometers
                distances.append((taxi_id, distance_km))

            distances.sort(key=lambda x: x[1])

            taxi_didapat = 0
            i = 0
            while(taxi_didapat < max_per_base and i < len(distances)):
                taxi_id, _ = distances[i]
                if taxi_id not in used_taxis:
                    used_taxis.add(taxi_id)
                    selected_taxis[str(taxi_id)] = taxi_current_state[str(taxi_id)]
                    taxi_didapat+=1
                i+=1

        return selected_taxis

    def periodic_call_agent(self):
        while not self.agent_stop_event.is_set():
            time.sleep(15)
            if self.normal_mode_active_event.is_set():
                try:
                    self.agent_running = True
                    
                    if self.agent_stop_event.is_set():
                        break
                        
                    print("STARTING PREC INTELLIGENT AGENT EXECUTION")
                    print("="*80)
                    
                    if self.intelligent_agent is None:
                        print("PREC intelligent agent not initialized, skipping cycle")
                        self.agent_running = False
                        continue
                    
                    def _get_agent_data():
                        try:
                            base_state_copy = dict(self.base_current_state.items())
                            taxi_state_copy = dict(self.taxi_current_state.items())
                            base_requests = list(self.base_request_data_now)
                            
                            base_requests = [str(base_id) for base_id in base_requests]
                            
                            self.data_manager.synchronize_requests_with_base_state()
                            
                            base_requests = list(self.base_request_data_now)
                            
                            base_requests_for_agent = []
                            for base_id_str in base_requests:
                                try:
                                    base_requests_for_agent.append(int(base_id_str))
                                except ValueError:
                                    pass
                            
                            base_requests = base_requests_for_agent

                            taxi_in_fleet = set()
                            for _, base in base_state_copy.items():
                                fleet = base.get('fleet', [])
                                if fleet:
                                    fleet_ids = [int(taxi_id) if isinstance(taxi_id, str) and taxi_id.isdigit() else taxi_id 
                                               for taxi_id in fleet if taxi_id is not None]
                                    taxi_in_fleet.update(fleet_ids)
                            
                            available_taxis = {}
                            for taxi_id, state in taxi_state_copy.items():
                                taxi_id_int = int(taxi_id) if isinstance(taxi_id, str) and str(taxi_id).isdigit() else taxi_id
                                
                                if (state.get('taxi_state') == 'kosong' and 
                                    taxi_id_int not in taxi_in_fleet and 
                                    taxi_id not in self.assignment_manager.active_assignments.keys() and
                                    state.get("battery") > BATTERY_TRESHOLD):
                                    available_taxis[taxi_id_int] = state
                            
                            return base_requests, available_taxis
                        except Exception as e:
                            print(f"Error getting agent data: {e}")
                            return [], {}

                    base_requests, available_taxis = safe_db_operation(_get_agent_data)
                    count_kosong = len(available_taxis)
                    
                    print(f"Agent Input Data:")
                    print(f"Available taxis: {count_kosong}")
                    print(f"Base requests: {len(base_requests)}")
                    print(f"Active assignments: {len(self.assignment_manager.active_assignments)}")
                    print(f"Active assignments array: {self.assignment_manager.active_assignments}")
                    print(f"current simulation_time: {get_current_sim_time()}")
                    
                    if count_kosong == 0 or len(base_requests) == 0:
                        print(f"Skipping PREC agent cycle: available taxis={count_kosong}, base requests={len(base_requests)}")
                        self.agent_running = False
                        continue
                    
                    top_order_rate = []
                    if count_kosong < len(base_requests):
                        try:
                            cached_base_order = {}
                            def safe_get_base_order_rate_wrapper(base_id):
                                try:
                                    if(base_id not in cached_base_order.keys()):
                                        rate = get_base_order_rate(base_id, API_ORDER_RATE_SIMULATION_URL)
                                        cached_base_order[str(base_id)] = rate
                                        return rate if rate is not None else 0
                                    else:
                                        rate = cached_base_order.get(str(base_id))
                                        return rate if rate is not None else 0
                                except Exception as e:
                                    print(f"Error getting base order rate for {base_id}: {e}")
                                    return 0
                            
                            top_order_rate = sorted(base_requests, key=safe_get_base_order_rate_wrapper, reverse=True)[:count_kosong]
                        except Exception as e:
                            print(f"Error sorting base requests: {e}")
                            top_order_rate = base_requests[:count_kosong]
                    else:
                        top_order_rate = base_requests

                    available_taxis = self.filter_nearest_taxis(
                        top_order_rates=top_order_rate, 
                        available_taxi_dict=available_taxis, 
                        max_per_base=10,
                        base_current_state=self.base_current_state,
                        taxi_current_state=self.taxi_current_state
                    )

                    print(f"Top order rate bases: {top_order_rate}")
                    print(f"Selected taxis: {list(available_taxis.keys())}")

                    if len(top_order_rate) > 0:
                        try:
                            print(f"Initializing PREC agent")
                            constraint_satisfied = self.intelligent_agent.initialize(
                                taxi_data=available_taxis,
                                requests=top_order_rate,
                                taxi_current_state=self.taxi_current_state,
                                base_current_state=self.base_current_state 
                            )
                            print(f"PREC agent initialization: {'SUCCESS' if constraint_satisfied else 'FAILED'}")
                        except Exception as e:
                            print(f"Error initializing PREC agent: {e}")
                            constraint_satisfied = False
                            
                        if constraint_satisfied:
                            try:
                                print(f"Starting PREC agent execution with comprehensive profiling...")
                                
                                profiler = cProfile.Profile()
                                profiler.enable()

                                res = self.intelligent_agent.run(
                                    num_of_cycle=NUM_OF_CYCLE,
                                    requests=top_order_rate,
                                    taxi_data=available_taxis,
                                    ec_probe_iteration=EC_PROBE_ITERATION
                                )

                                profiler.disable()
                                
                                print(f"PREC agent execution completed!: {res}")
                                analyze_and_print_profile(profiler)
                                
                            except Exception as e:
                                print(f"Error running PREC agent: {e}")
                                self.agent_running = False
                                continue
                                
                            config = res.get('configuration', {})
                            fitness = res.get("fitness")
                            
                            if fitness is not None and fitness >= 0:
                                print(f"PREC agent found solution with fitness {fitness}")
                                self.assignment_manager.assignment_map.clear()

                                assignments_for_simulations = []

                                for taxi_id, base_id in config.items():
                                    try:
                                        taxi_id_str = str(taxi_id)
                                        base_id_int = int(base_id) if isinstance(base_id, str) else base_id
                                        
                                        def _remove_base_request():
                                            try:
                                                base_id_str = str(base_id_int)
                                                if base_id_str in self.base_request_data_now:
                                                    self.base_request_data_now.remove(base_id_str)
                                                elif base_id_int in self.base_request_data_now:
                                                    self.base_request_data_now.remove(base_id_int)
                                                return True
                                            except Exception as e:
                                                print(f"Error removing base {base_id_int} from requests: {e}")
                                                return False
                                        
                                        safe_db_operation(_remove_base_request)
                                        
                                        taxi = available_taxis.get(taxi_id)
                                        def _get_base_state():
                                            try:
                                                return self.base_current_state.get(str(base_id_int))
                                            except Exception as e:
                                                print(f"Error getting base {base_id_int} state: {e}")
                                                return None
                                        
                                        base = safe_db_operation(_get_base_state)
                                        
                                        if not taxi or not base:
                                            print(f"Taxi {taxi_id} or base {base_id_int} not found")
                                            continue
                                            
                                        taxi_coords = (taxi.get('latitude', 0), taxi.get('longitude', 0))
                                        base_coords = (base.get('latitude', 0), base.get('longitude', 0))
                                        
                                        poly, encoded_route_node_id = get_route_polyline(
                                            coordAwal=taxi_coords, 
                                            coordAkhir=base_coords,
                                            api_gmaps_simulation_url=API_GMAPS_SIMULATION_URL
                                        )
                                        
                                        if not poly:
                                            print(f"Could not get polyline for taxi {taxi_id} to base {base_id_int}")
                                            continue
                                            
                                        self.assignment_manager.assignment_map[taxi_id_str] = {
                                            'base_id': base_id_int, 
                                            'polyline': poly
                                        }
                                        
                                        payload = {
                                            'taxi_id': taxi_id_str,
                                            'assigned_base': str(base_id_int), 
                                            'polyline': poly, 
                                            "deviate_radius": MELENCENG_RADIUS,
                                            'encoded_route_node_id': encoded_route_node_id
                                        }
                                        assignments_for_simulations.append(payload)
                                        
                                        print(f"Assignment created: Taxi {taxi_id_str} -> Base {base_id_int}")
                                        
                                        sid_fe = self.connected_clients_map_frontend.get(taxi_id_str)
                                        print(f"client map : {self.connected_clients_map_frontend}")
                                        print(f"sid_fe: {sid_fe}")
                                        print(f"taxi_id string: {taxi_id_str}")
                                        if sid_fe:
                                            try:
                                                self.socketio.emit('assign_base', payload, to=sid_fe)
                                                print(f" Sent assignment to frontend for taxi {taxi_id_str}")
                                            except Exception as e:
                                                print(f"Error sending assignment to frontend for taxi {taxi_id_str}: {e}")
                                                
                                    except Exception as e:
                                        print(f"Error processing assignment for taxi {taxi_id}: {e}")
                                        continue
                                        
                                mqtt_simulation_payload = {"message": assignments_for_simulations}
                                self.mqtt_handler.send_mqtt(
                                    topic=TOPIC_TAXI_ASSIGNMENT,
                                    dictionary=mqtt_simulation_payload
                                )
                                
                                print(f"Creating watchers for {len(self.assignment_manager.assignment_map)} assignments")
                                self.assignment_manager.notice_assignment(
                                    assignments=self.assignment_manager.assignment_map,
                                    radius=MELENCENG_RADIUS,
                                    travel_duration_margin=TRAVEL_DURATION_MARGIN,
                                    api_gmaps_simulation_url=API_GMAPS_SIMULATION_URL
                                )
                                
                                print(f"Successfully processed {len(assignments_for_simulations)} assignments")
                            else:
                                print("PREC agent: No constraint satisfied solution")
                        else:
                            print("PREC agent: No constraint satisfied solution")
                    
                    print("Periodic PREC agent call completed")
                    print("="*80 + "\n")
                    self.agent_running = False
                    
                except Exception as e:
                    print(f"Error in periodic_call_agent: {e}")
                    self.agent_running = False
                    time.sleep(15)
            else:
                
                self.normal_mode_active_event.wait(timeout=1)

    def start_periodic_agent(self):
        try:
            if self.agent_thread is None or not self.agent_thread.is_alive():
                self.agent_stop_event.clear()
                self.agent_thread = threading.Thread(target=self.periodic_call_agent, daemon=True)
                self.agent_thread.start()
        except Exception as e:
            logger.error(f"Error starting periodic agent: {e}")

    def stop_periodic_agent(self):
        try:
            self.agent_stop_event.set()
        except Exception as e:
            logger.error(f"Error stopping periodic agent: {e}")
