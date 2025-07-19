import json
import logging
import paho.mqtt.client as mqtt
from datetime import datetime
from zoneinfo import ZoneInfo
from collections import Counter
import time
import copy
import traceback

from config.settings import *
from utils.simulation_time import update_sim_time
from utils.database import safe_db_operation
from utils.api_client import get_base_order_rate, get_route_polyline
from core.intelligent_agent_manager import IntelligentAgentManager

logger = logging.getLogger(__name__)

class MQTTHandler:
    def __init__(self, data_manager, assignment_manager, taxi_current_state, 
                 base_current_state, log_base_activity, in_base_area_map, 
                 connected_clients_map_frontend, socketio,
                 intelligent_agent_instance, normal_mode_active_event, simulation_mode_active_event, socketio_handler):
        self.data_manager = data_manager
        self.assignment_manager = assignment_manager
        self.taxi_current_state = taxi_current_state
        self.base_current_state = base_current_state
        self.log_base_activity = log_base_activity
        self.in_base_area_map = in_base_area_map 
        self.connected_clients_map_frontend = connected_clients_map_frontend 
        self.socketio = socketio 
        self.intelligent_agent = intelligent_agent_instance
        self.normal_mode_active_event = normal_mode_active_event
        self.simulation_mode_active_event = simulation_mode_active_event
        
        self.client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_disconnect = self.on_disconnect

        self.last_assignment_request_data = None
        self.mqtt_reconnection_count = 0 
        self.socketio_handler = socketio_handler

    def send_mqtt(self, topic, dictionary):
        payload = json.dumps(dictionary)
        self.client.publish(topic, payload)

    def on_connect(self, client, userdata, flags, rc, properties=None):
        try:
            if rc == 0:
                logger.info("Connected to MQTT broker successfully")
                client.subscribe([
                    (TOPIC_GPS, 0), 
                    (TOPIC_BASE_REQUEST, 0), 
                    (TOPIC_BASE_CHANGE, 0), 
                    (TOPIC_BASE_REGISTER, 0),
                    (TOPIC_ASSIGNMENT_REQUEST, 0),
                    (TOPIC_RESET_MQTT, 0)
                ])
                
                self.mqtt_reconnection_count += 1 
                if self.mqtt_reconnection_count > 1:
                    logger.info(f"MQTT reconnection detected (count: {self.mqtt_reconnection_count})")
                    
                    if self.last_assignment_request_data:
                        logger.info("Triggering assignment request resend due to reconnection")
                        self._handle_simulation_assignment_request(self.last_assignment_request_data)
            else:
                logger.error(f"Failed to connect to MQTT broker, return code {rc}")
        except Exception as e:
            logger.error(f"Error in on_connect: {e}")

    def on_message(self, *args):
        try:
            if len(args) < 3:
                return
                    
            client, userdata, msg = args
                
            try:
                payload = json.loads(msg.payload.decode())
            except json.JSONDecodeError as e:
                logger.error(f"Error decoding JSON payload: {e}")
                return
                
            if 'sim_time' in payload:
                update_sim_time(payload['sim_time'])
                    
            if msg.topic == TOPIC_ASSIGNMENT_REQUEST:
                self.normal_mode_active_event.clear()
                self.simulation_mode_active_event.set()
                self._handle_simulation_assignment_request(payload)
            elif msg.topic == TOPIC_RESET_MQTT:
                self.simulation_mode_active_event.clear()
                self.normal_mode_active_event.set()
            elif msg.topic == TOPIC_GPS:
                self.simulation_mode_active_event.clear()
                self.normal_mode_active_event.set()
                self.handle_gps_message(payload)
            elif msg.topic == TOPIC_BASE_REQUEST:
                self.simulation_mode_active_event.clear()
                self.normal_mode_active_event.set()
                self.handle_base_request_message(payload)
            elif msg.topic == TOPIC_BASE_CHANGE:
                self.simulation_mode_active_event.clear()
                self.normal_mode_active_event.set()
                self.handle_base_change_message(payload)
            elif msg.topic == TOPIC_BASE_REGISTER:
                self.simulation_mode_active_event.clear()
                self.normal_mode_active_event.set()
                self.handle_base_register_message(payload)
                    
        except Exception as e:
            logger.error(f"Error processing MQTT message: {e}")
            logger.error(traceback.format_exc())

    def _handle_simulation_assignment_request(self, payload):
        self.last_assignment_request_data = copy.deepcopy(payload)
        request_start_time = time.time()
        
        logger.info("Starting PREC Intelligent Agent Execution")
        
        if self.intelligent_agent is None:
            logger.error("PREC intelligent agent not initialized")
            self._send_assignment_response({
                'assignments': [],
                'error': 'Intelligent agent not initialized',
                'processing_time': 0
            })
            return
        
        simulation_taxi_data = payload.get('taxi_data', {})
        simulation_base_data = payload.get('base_data', {})
        
        old_base_fleets_snapshot = {
            base_id: list(base_info.get('fleet', []))
            for base_id, base_info in self.base_current_state.items()
        }


        def _update_backend_state():
            try:
                for taxi_id, taxi_info in simulation_taxi_data.items():
                    self.taxi_current_state[str(taxi_id)] = {
                        "taxi_state": taxi_info.get("taxi_state", "kosong"),
                        "latitude": taxi_info.get("latitude", 0.0),
                        "longitude": taxi_info.get("longitude", 0.0),
                        "battery": taxi_info.get("battery", 100.0)
                    }
                for base_id, base_info in simulation_base_data.items():
                    self.base_current_state[str(base_id)] = {
                        'latitude': base_info.get("latitude", 0.0),
                        'longitude': base_info.get("longitude", 0.0),
                        'fleet': base_info.get("fleet", [])
                    }
                return True
            except Exception as e:
                logger.error(f"Error updating backend state: {e}")
                return False

        if not safe_db_operation(_update_backend_state):
            self._send_assignment_response({
                'assignments': [],
                'error': 'Failed to update backend state',
                'processing_time': 0
            })
            return

        self.data_manager.synchronize_requests_with_base_state()
        
        def _get_agent_data():
            try:
                base_state_copy = dict(self.base_current_state.items())
                taxi_state_copy = dict(self.taxi_current_state.items()[:1500])
                base_requests = list(self.data_manager.base_request_data_now)
                
                base_requests = [str(base_id) for base_id in base_requests]
                
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
                        state.get("battery", 0) > BATTERY_TRESHOLD):
                        available_taxis[taxi_id_int] = state
                
                return base_requests, available_taxis
            except Exception as e:
                logger.error(f"Error getting agent data: {e}")
                traceback.print_exc()
                return [], {}

        base_requests, available_taxis = safe_db_operation(_get_agent_data)
        count_kosong = len(available_taxis)
        
        if count_kosong == 0 or len(base_requests) == 0:
            logger.info(f"No assignments needed")
            processing_time = time.time() - request_start_time
            self._send_assignment_response({
                'assignments': [],
                'message': 'No assignments needed',
                'available_taxis': count_kosong,
                'base_requests': len(base_requests),
                'processing_time': processing_time
            })
            return
        
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
                        logger.error(f"Error getting base order rate for {base_id}: {e}")
                        return 0
                
                top_order_rate = sorted(base_requests, key=safe_get_base_order_rate_wrapper, reverse=True)[:count_kosong]
            except Exception as e:
                logger.error(f"Error sorting base requests: {e}")
                top_order_rate = base_requests[:count_kosong]
        else:
            top_order_rate = base_requests

        available_taxis = IntelligentAgentManager.filter_nearest_taxis(
            top_order_rates=top_order_rate, 
            available_taxi_dict=available_taxis, 
            max_per_base=10,
            base_current_state=self.base_current_state,
            taxi_current_state=self.taxi_current_state
        )


        if len(top_order_rate) > 0:
            try:
                logger.info(f"Initializing PREC agent")
                constraint_satisfied = self.intelligent_agent.initialize(
                    taxi_data=available_taxis,
                    requests=top_order_rate,
                    taxi_current_state=self.taxi_current_state,
                    base_current_state=self.base_current_state 
                )
                logger.info(f"PREC agent initialization: {'SUCCESS' if constraint_satisfied else 'FAILED'}")
            except Exception as e:
                logger.error(f"Error initializing PREC agent: {e}")
                traceback.print_exc()
                constraint_satisfied = False
                
            if constraint_satisfied:
                try:
                    logger.info(f"Starting PREC agent execution")
                    res = self.intelligent_agent.run(
                        num_of_cycle=NUM_OF_CYCLE,
                        requests=top_order_rate,
                        taxi_data=available_taxis,
                        ec_probe_iteration=EC_PROBE_ITERATION
                    )
                    logger.info(f"PREC agent execution completed")
                    
                except Exception as e:
                    logger.error(f"Error running PREC agent: {e}")
                    traceback.print_exc()
                    processing_time = time.time() - request_start_time
                    self._send_assignment_response({
                        'assignments': [],
                        'error': 'PREC agent execution failed',
                        'processing_time': processing_time
                    })
                    return
                    
                config = res.get('configuration', {})
                fitness = res.get("fitness")
                
                if fitness is not None and fitness >= 0:
                    logger.info(f"PREC agent found solution with fitness {fitness}")
                    
                    assignments_for_simulation = []

                    for taxi_id, base_id in config.items():
                        try:
                            taxi_id_str = str(taxi_id)
                            base_id_int = int(base_id) if isinstance(base_id, str) else base_id
                            
                            def _remove_base_request():
                                try:
                                    base_id_str_req = str(base_id_int)
                                    if base_id_str_req in self.data_manager.base_request_data_now:
                                        self.data_manager.base_request_data_now.remove(base_id_str_req)
                                    elif base_id_int in self.data_manager.base_request_data_now:
                                        self.data_manager.base_request_data_now.remove(base_id_int)
                                    return True
                                except Exception as e:
                                    logger.error(f"Error removing base {base_id_int} from requests: {e}")
                                    return False
                            
                            safe_db_operation(_remove_base_request)
                            
                            taxi = available_taxis.get(taxi_id)
                            def _get_base_state():
                                try:
                                    return self.base_current_state.get(str(base_id_int))
                                except Exception as e:
                                    logger.error(f"Error getting base {base_id_int} state: {e}")
                                    return None
                            
                            base = safe_db_operation(_get_base_state)
                            
                            if not taxi or not base:
                                logger.warning(f"Taxi {taxi_id} or base {base_id_int} not found")
                                continue
                                
                            taxi_coords = (taxi.get('latitude'), taxi.get('longitude'))
                            base_coords = (base.get('latitude'), base.get('longitude'))
                            
                            poly, encoded_route_node_id = get_route_polyline(
                                coordAwal=taxi_coords, 
                                coordAkhir=base_coords,
                                api_gmaps_simulation_url=API_GMAPS_SIMULATION_URL
                            )
                            
                            if not poly:
                                logger.warning(f"Could not get polyline for taxi {taxi_id} to base {base_id_int}")
                                continue
                                
                            assignment = {
                                'taxi_id': taxi_id_str,
                                'assigned_base': str(base_id_int), 
                                'polyline': poly, 
                                "deviate_radius": MELENCENG_RADIUS,
                                'encoded_route_node_id': encoded_route_node_id
                            }
                            assignments_for_simulation.append(assignment)
                            
                            logger.info(f"Assignment created: Taxi {taxi_id_str} -> Base {base_id_int}")
                            
                        except Exception as e:
                            logger.error(f"Error processing assignment for taxi {taxi_id}: {e}")
                            traceback.print_exc()
                            continue
                    
                    logger.info(f"Successfully processed {len(assignments_for_simulation)} assignments")
                    
                    
                    now_wib = datetime.now(ZoneInfo("Asia/Jakarta"))
                    
                    for base_id_str, new_base_info_from_payload in simulation_base_data.items():
                        
                        old_fleet_set = set(old_base_fleets_snapshot.get(base_id_str, []))
                        new_fleet_set = set(new_base_info_from_payload.get('fleet', []))

                        
                        old_fleet_filtered = {t for t in old_fleet_set if t is not None}
                        new_fleet_filtered = {t for t in new_fleet_set if t is not None}

                        taxis_entered = new_fleet_filtered - old_fleet_filtered
                        taxis_left = old_fleet_filtered - new_fleet_filtered

                        for taxi_id in taxis_entered:
                            def _log_taxi_in():
                                self.log_base_activity.add_record(
                                    timestamp=now_wib,
                                    base_id=base_id_str,
                                    status="taxi masuk",
                                    taxi_id=taxi_id
                                )
                                return True
                            safe_db_operation(_log_taxi_in)

                        for taxi_id in taxis_left:
                            def _log_taxi_out():
                                self.log_base_activity.add_record(
                                    timestamp=now_wib,
                                    base_id=base_id_str,
                                    status="taxi keluar",
                                    taxi_id=taxi_id
                                )
                                return True
                            safe_db_operation(_log_taxi_out)


                    processing_time = time.time() - request_start_time
                    self._send_assignment_response({
                        'assignments': assignments_for_simulation,
                        'fitness': fitness,
                        'total_assignments': len(assignments_for_simulation),
                        'message': 'Assignment successful',
                        'processing_time': processing_time
                    })
                else:
                    logger.warning("PREC agent: No constraint satisfied solution")
                    processing_time = time.time() - request_start_time
                    self._send_assignment_response({
                        'assignments': [],
                        'message': 'No constraint satisfied solution found',
                        'processing_time': processing_time
                    })
            else:
                logger.warning("PREC agent: Initialization failed")
                processing_time = time.time() - request_start_time
                self._send_assignment_response({
                    'assignments': [],
                    'message': 'PREC agent initialization failed',
                    'processing_time': processing_time
                })
        else:
            processing_time = time.time() - request_start_time
            self._send_assignment_response({
                'assignments': [],
                'message': 'No bases to assign',
                'processing_time': processing_time
            })
            
    def _send_assignment_response(self, response_data):
        try:
            if self.client and self.client.is_connected():
                message = json.dumps(response_data)
                self.client.publish(TOPIC_ASSIGNMENT_RESPONSE, message)
                logger.info(f"Sent assignment response with {len(response_data.get('assignments', []))} assignments to simulation")
                self.socketio_handler.send_operator_update()
            else:
                logger.error("MQTT client not connected, cannot send response")
        except Exception as e:
            logger.error(f"Error sending MQTT response: {e}")

    def handle_gps_message(self, payload):
        try:
            taxi_id = payload.get("taxi_id")
            if taxi_id is None:
                return
                
            def _update_taxi_state():
                try:
                    self.taxi_current_state[str(taxi_id)] = {
                        "taxi_state": payload.get("taxi_state"),
                        "latitude": payload.get("latitude"),
                        "longitude": payload.get("longitude"),
                        "battery": payload.get("battery")
                    }
                    return True
                except Exception as e:
                    return False

            
            safe_db_operation(_update_taxi_state)

        except Exception as e:
            logger.error(f"Error in handle_gps_message: {e}")

    def handle_base_request_message(self, payload):
        try:
            base_id = payload.get("base_id")
            if base_id is None:
                return
                
            def _add_requests():
                try:
                    requests_to_add = payload.get('requests', 0)
                    for _ in range(requests_to_add):
                        self.data_manager.safely_add_base_request(base_id)
                    return True
                except Exception as e:
                    return False
            
            safe_db_operation(_add_requests)
            
            def _sync_requests():
                try:
                    self.data_manager.synchronize_requests_with_base_state()
                    return True
                except Exception as e:
                    return False
            
            safe_db_operation(_sync_requests)
            
        except Exception as e:
            logger.error(f"Error in handle_base_request_message: {e}")

    def handle_base_change_message(self, payload):
        try:
            base_id = payload.get("base_id")
            print("base 1")
            if base_id is None:
                return
            print("base 2")
                
            def _update_base_state():
                try:
                    base_fleet_awal = self.base_current_state.get(str(base_id), {}).get("fleet", [])
                    
                    self.base_current_state[str(base_id)] = {
                        'latitude': payload.get("base_latitude"),
                        'longitude': payload.get("base_longitude"),
                        'fleet': payload.get("base_fleet"),
                    }
                    
                    new_fleet = self.base_current_state.get(str(base_id), {}).get("fleet", [])
                    return base_fleet_awal, new_fleet
                except Exception as e:
                    return [], []

            print("base 3")
            base_fleet_awal, new_fleet = safe_db_operation(_update_base_state)
            print("base 4")
            
            self._process_fleet_changes(base_id, base_fleet_awal, new_fleet)
            print("base 5")
            
            def _sync_requests():
                try:
                    self.data_manager.synchronize_requests_with_base_state()
                    return True
                except Exception as e:
                    return False
            
            safe_db_operation(_sync_requests)
            
        except Exception as e:
            logger.error(f"Error in handle_base_change_message: {e}")

    def handle_base_register_message(self, payload):
        try:
            base_id = payload.get("base_id")
            if base_id is None:
                return
                
            def _register_base():
                try:
                    self.base_current_state[str(base_id)] = {
                        'latitude': payload.get("base_latitude"),
                        'longitude': payload.get("base_longitude"),
                        'fleet': payload.get("base_fleet"),
                    }
                    return True
                except Exception as e:
                    return False
            
            safe_db_operation(_register_base)

            def _sync_requests():
                try:
                    self.data_manager.synchronize_requests_with_base_state()
                    return True
                except Exception as e:
                    return False
            
            safe_db_operation(_sync_requests)
            
        except Exception as e:
            logger.error(f"Error in handle_base_register_message: {e}")

    def _process_fleet_changes(self, base_id, base_fleet_awal, new_fleet):
        try:
            jumlah_taxi_awal = len([x for x in base_fleet_awal if x is not None]) if base_fleet_awal else 0
            jumlah_taxi_akhir = len([x for x in new_fleet if x is not None]) if new_fleet else 0
        
            if jumlah_taxi_akhir > jumlah_taxi_awal:
                entered_taxis = set([x for x in new_fleet if x is not None]) - set([x for x in base_fleet_awal if x is not None])
            
                for arrived_taxi in entered_taxis:
                    now_wib = datetime.now(ZoneInfo("Asia/Jakarta"))
                
                    def _log_entry():
                        try:
                            self.log_base_activity.add_record(
                                timestamp=now_wib,
                                base_id=base_id,
                                status="taxi masuk", 
                                taxi_id=arrived_taxi
                            )
                            return True
                        except Exception as e:
                            return False
                    
                    safe_db_operation(_log_entry)
                
                    print("1")
                    self.assignment_manager.cancel_taxi_assignment(arrived_taxi)
                    print("2")
                    if arrived_taxi not in self.assignment_manager.active_assignments:
                        print("3")
                        for other_taxi_id, assignment in list(self.assignment_manager.active_assignments.items()):
                            print("4")
                            print(f"other_taxi_id: {other_taxi_id}")
                            print(f"arrived: {arrived_taxi}")
                            print(f"base_id di assignment.get(): {assignment.get('base_id')}")
                            print(f"base_id: {base_id}")
                            if other_taxi_id != arrived_taxi and str(assignment.get('base_id')) == str(base_id):
                                print("5")
                                self.assignment_manager.cancel_taxi_assignment(other_taxi_id)
                                print("6")
                            
                                sid_fe = self.connected_clients_map_frontend.get(str(other_taxi_id))
                                print("HALOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO")
                                if sid_fe:
                                    print("HAIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII")
                                    try:
                                        notification = {
                                            'type': 'cancel_assignment',
                                            'message': f'Your assignment to base {base_id} has been cancelled because another taxi arrived'
                                        }
                                        self.socketio.emit('notification', notification, to=sid_fe)
                                    except Exception as e:
                                        pass
                    else:
                        is_assigned_to_base_terkait = self.assignment_manager.is_taxi_assigned_to_base(
                            taxi_id=arrived_taxi, 
                            target_base_id=base_id
                        )
                        if is_assigned_to_base_terkait:
                            self.assignment_manager.cancel_taxi_assignment(arrived_taxi)
        
            if jumlah_taxi_akhir < jumlah_taxi_awal:
                left_taxis = set([x for x in base_fleet_awal if x is not None]) - set([x for x in new_fleet if x is not None])
            
                for left_taxi in left_taxis:
                    now_wib = datetime.now(ZoneInfo("Asia/Jakarta"))
                
                    def _log_exit():
                        try:
                            self.log_base_activity.add_record(
                                timestamp=now_wib,
                                base_id=base_id,
                                status="taxi keluar", 
                                taxi_id=left_taxi
                            )
                            return True
                        except Exception as e:
                            return False
                    
                    safe_db_operation(_log_exit)
                
                    def _add_base_back():
                        try:
                            return self.data_manager.safely_add_base_request(base_id)
                        except Exception as e:
                            return False
                
                    safe_db_operation(_add_base_back)
                
        except Exception as e:
            logger.error(f"Error processing fleet changes: {e}")

    def on_disconnect(self, client, userdata, flags, rc, properties=None):
        if rc != 0:
            print(f"Unexpected disconnection (rc={rc}). Attempting to reconnect...")

    def start_mqtt_thread(self):
        import time
        max_retries = 10
        retry_count = 0

        while retry_count < max_retries:
            try:
                self.client.connect(MQTT_BROKER, MQTT_PORT, 60)
                self.client.loop_forever()
                break
            except Exception as e:
                retry_count += 1
                print(f"Error in MQTT thread (attempt {retry_count}/{max_retries}): {e}")
                if retry_count < max_retries:
                    print(f"Retrying MQTT connection in 5 seconds...")
                    time.sleep(5)
                else:
                    print("Max MQTT connection retries exceeded.")
