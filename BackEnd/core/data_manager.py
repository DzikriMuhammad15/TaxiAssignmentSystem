import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from collections import Counter
from utils.database import safe_db_operation
from utils.geo_utils import jarak_radius, getNearestBase
from assets.graph import get_nearest_node, G

logger = logging.getLogger(__name__)

class DataManager:
    def __init__(self, base_current_state, taxi_current_state, base_request_data_now, 
                 base_reference_data, taxi_reference_data, log_base_activity):
        self.base_current_state = base_current_state
        self.taxi_current_state = taxi_current_state
        self.base_request_data_now = base_request_data_now
        self.base_reference_data = base_reference_data
        self.taxi_reference_data = taxi_reference_data
        self.log_base_activity = log_base_activity

    def init_data(self, base_data_init, jumlah_taxi):
        def _init_operation():
            try:
                dikunjungi = []
                
                for base in base_data_init:
                    base_id = get_nearest_node(lat=base.get("latitude"), lon=base.get("longitude"), G=G)
                    logger.info(f"Initializing base: {base.get('name')} with ID {base_id}")
                    
                    if base_id not in dikunjungi:
                        dikunjungi.append(base_id)
                        fleet = [None] * base.get("capacity")
                        self.base_current_state[str(base_id)] = {
                            'latitude': base.get("latitude"),
                            'longitude': base.get("longitude"),
                            'fleet': fleet,
                        }
                        self.base_reference_data.add_base(str(base_id))
                
                for i in range(jumlah_taxi):
                    taxi_id = i
                    self.taxi_current_state[str(taxi_id)] = {
                        "taxi_state": "kosong",
                        "latitude": 0.0,
                        "longitude": 0.0,
                        "battery": 0.0
                    }
                    self.taxi_reference_data.add_taxi(str(taxi_id))
                
                return True
            except Exception as e:
                logger.error(f"Error in init_data operation: {e}")
                return False

        try:
            return safe_db_operation(_init_operation)
        except Exception as e:
            logger.error(f"Failed to initialize data: {e}")
            return False

    def synchronize_requests_with_base_state(self):
        try:
            try:
                current_requests_list = list(self.base_request_data_now)
            except Exception as e:
                current_requests_list = []
            
            normalized_requests = []
            for req in current_requests_list:
                req_str = str(req)
                normalized_requests.append(req_str)
            
            try:
                self.base_request_data_now.clear()
            except AttributeError:
                try:
                    while len(self.base_request_data_now) > 0:
                        self.base_request_data_now.pop(0)
                except Exception as e:
                    pass
            
            request_count = Counter(normalized_requests)
            
            total_added = 0
            for base_id_str, state in self.base_current_state.items():
                fleet = state.get('fleet', [])
                if fleet:
                    empty_slots = fleet.count(None)
                    for _ in range(empty_slots):
                        self.base_request_data_now.append(base_id_str)
                        total_added += 1
                        
        except Exception as e:
            logger.error(f"Error in synchronize_requests_with_base_state: {e}")

    def safely_add_base_request(self, base_id):
        try:
            base_id_str = str(base_id)
            base_state = self.base_current_state.get(base_id_str)
            if not base_state:
                return False
                
            fleet = base_state.get('fleet', [])
            empty_slots = fleet.count(None)
            
            try:
                current_requests_list = list(self.base_request_data_now)
                current_requests = current_requests_list.count(base_id_str)
                try:
                    base_id_int = int(base_id_str)
                    current_requests += current_requests_list.count(base_id_int)
                except ValueError:
                    pass
            except Exception as e:
                current_requests = 0
            
            if empty_slots > current_requests:
                self.base_request_data_now.append(base_id_str)
                return True
            else:
                return False
        except Exception as e:
            return False

    def isInBaseArea(self, coordTaxi, base_id, base_radius):
        def _check_operation():
            try:
                base = self.base_current_state.get(str(base_id))
                if not base:
                    return False
                    
                base_lat = base.get("latitude")
                base_lon = base.get("longitude")
                
                if base_lat is None or base_lon is None:
                    return False
                    
                radius = jarak_radius(coordTaxi, (base_lat, base_lon))
                return radius <= base_radius
            except Exception as e:
                return False

        try:
            return safe_db_operation(_check_operation)
        except Exception as e:
            return False

    def availableSlot(self, base_id):
        try:
            if str(base_id) not in self.base_current_state:
                return False
            
            fleet = self.base_current_state[str(base_id)].get("fleet", [])
            if not fleet:
                return False
                
            return any(slot is None for slot in fleet)
        except Exception as e:
            return False

    def is_taxi_in_base_fleet(self, taxi_id):
        def _check_taxi_in_fleet():
            try:
                taxi_id_str = str(taxi_id)
                
                for base_id, base_state in self.base_current_state.items():
                    fleet = base_state.get('fleet', [])
                    if fleet:
                        for slot_taxi in fleet:
                            if slot_taxi is not None and str(slot_taxi) == taxi_id_str:
                                return True
                
                return False
            except Exception as e:
                logger.error(f"Error checking if taxi {taxi_id} is in base fleet: {e}")
                return False
        
        try:
            return safe_db_operation(_check_taxi_in_fleet)
        except Exception as e:
            logger.error(f"Error in is_taxi_in_base_fleet for taxi {taxi_id}: {e}")
            return False

    def add_taxi_to_base(self, taxi_id, base_id):
        def _add_operation():
            try:
                base_state = self.base_current_state.get(str(base_id))
                if base_state is None:
                    return False

                fleet = base_state.get('fleet', [])
                if None not in fleet:
                    return False

                for i in range(len(fleet)):
                    if fleet[i] is None:
                        fleet[i] = taxi_id
                        break

                self.base_current_state[str(base_id)] = {
                    'latitude': base_state['latitude'],
                    'longitude': base_state['longitude'],
                    'fleet': fleet
                }

                now_wib = datetime.now(ZoneInfo("Asia/Jakarta"))
                try:
                    self.log_base_activity.add_record(
                        timestamp=now_wib,
                        base_id=base_id,
                        status="taxi masuk", 
                        taxi_id=taxi_id
                    )
                except Exception as e:
                    pass

                return True
                
            except Exception as e:
                return False

        try:
            return safe_db_operation(_add_operation)
        except Exception as e:
            return False

    def replace_one_value_with_none(self, arr, target_value):
        try:
            for i in range(len(arr)):
                if arr[i] == target_value:
                    arr[i] = None
                    break
        except Exception as e:
            pass
