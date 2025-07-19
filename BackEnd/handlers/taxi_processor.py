import threading
import time
import polyline
import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from utils.geo_utils import is_melenceng
from utils.simulation_time import get_current_sim_time
from config.settings import BASE_RADIUS, MELENCENG_RADIUS
from utils.database import safe_db_operation
from utils.geo_utils import getNearestBase

logger = logging.getLogger(__name__)

class TaxiProcessor:
    def __init__(self, data_manager, assignment_manager, taxi_current_state, 
                 base_current_state, log_base_activity, log_pelanggaran_data,
                 connected_clients_map_frontend, socketio, in_base_area_map,
                 normal_mode_active_event):
        self.data_manager = data_manager
        self.assignment_manager = assignment_manager
        self.taxi_current_state = taxi_current_state
        self.base_current_state = base_current_state
        self.log_base_activity = log_base_activity
        self.log_pelanggaran_data = log_pelanggaran_data
        self.connected_clients_map_frontend = connected_clients_map_frontend
        self.socketio = socketio
        self.in_base_area_map = in_base_area_map
        self.normal_mode_active_event = normal_mode_active_event

    def find_base_area_for_taxi(self, taxi_id):
        for base_id, taxi_list in self.in_base_area_map.items():
            if taxi_id in taxi_list:
                return base_id
        return None

    def find_base_checked_in_for_taxi(self, taxi_id):
        for base_id, base_data in self.base_current_state.items():
            base_fleet = base_data.get("fleet")
            if taxi_id in base_fleet:
                return base_id
        return None

    def process_data_taxi(self):
        while True:
            
            if self.normal_mode_active_event.is_set():
                for taxi_id in self.taxi_current_state.keys():
                    try:
                        payload = self.taxi_current_state.get(taxi_id)
                        
                        def _get_bases():
                            try:
                                return dict(self.base_current_state.items())
                            except Exception as e:
                                return {}

                        bases = safe_db_operation(_get_bases)
                        if not bases:
                            continue
                            
                        taxi_coords = (payload.get("latitude"), payload.get("longitude"))
                        nearest_base = getNearestBase(coord_taxi=taxi_coords, bases=bases)
                        
                        if not nearest_base:
                            continue
                        
                        in_base_area = self.data_manager.isInBaseArea(coordTaxi=taxi_coords, base_id=nearest_base, base_radius=BASE_RADIUS)
                        already_in_base = self.data_manager.is_taxi_in_base_fleet(taxi_id=taxi_id)

                        if not already_in_base:
                            is_base_available = self.data_manager.availableSlot(base_id=nearest_base)
                            
                            if in_base_area and is_base_available:
                                if nearest_base not in self.in_base_area_map:
                                    self.in_base_area_map[nearest_base] = [taxi_id]
                                else:
                                    if taxi_id not in self.in_base_area_map.get(nearest_base, []):
                                        self.in_base_area_map.get(nearest_base).append(taxi_id)
                                
                                sid_fe = self.connected_clients_map_frontend.get(str(taxi_id))
                                if sid_fe:
                                    try:
                                        notification = {
                                            'type': 'in_base_area',
                                            'base_id': nearest_base,
                                            'message': f'You are in the area of base {nearest_base}. You can scan QR code to check in.'
                                        }
                                        self.socketio.emit('notification', notification, to=sid_fe)
                                        print("terkirim")
                                    except Exception as e:
                                        pass

                        base_area_taxi = self.find_base_area_for_taxi(taxi_id)
                        if base_area_taxi is not None:
                            in_base_area_taxi = self.data_manager.isInBaseArea(coordTaxi=taxi_coords, base_id=base_area_taxi, base_radius=BASE_RADIUS)
                            if not in_base_area_taxi:
                                if base_area_taxi in self.in_base_area_map and taxi_id in self.in_base_area_map[base_area_taxi]:
                                    self.in_base_area_map.get(base_area_taxi).remove(taxi_id)

                        base_slot_taxi = self.find_base_checked_in_for_taxi(taxi_id)
                        if base_slot_taxi is not None:
                            in_base_slot_taxi = self.data_manager.isInBaseArea(coordTaxi=taxi_coords, base_id=base_slot_taxi, base_radius=BASE_RADIUS)
                            if not in_base_slot_taxi:
                                def _handle_taxi_leaving():
                                    try:
                                        base_fleet = self.base_current_state.get(str(base_slot_taxi), {}).get("fleet", [])
                                        if base_fleet and taxi_id in base_fleet:
                                            
                                            self.data_manager.replace_one_value_with_none(arr=base_fleet, target_value=taxi_id)
                                            
                                            count_none = base_fleet.count(None)
                                            self.base_current_state[str(base_slot_taxi)] = {
                                                "latitude": self.base_current_state[str(base_slot_taxi)].get("latitude"),
                                                "longitude": self.base_current_state[str(base_slot_taxi)].get("longitude"),
                                                "fleet": [x for x in base_fleet if x is not None] + [None] * count_none
                                            }
                                            
                                            now_wib = datetime.now(ZoneInfo("Asia/Jakarta"))
                                            try:
                                                self.log_base_activity.add_record(
                                                    timestamp=now_wib,
                                                    base_id=base_slot_taxi,
                                                    status="taxi keluar", 
                                                    taxi_id=taxi_id
                                                )
                                            except Exception as e:
                                                pass
                                                
                                            self.data_manager.safely_add_base_request(base_slot_taxi)
                                            return True
                                        return False
                                    except Exception as e:
                                        return False
                                safe_db_operation(_handle_taxi_leaving)

                        if taxi_id in self.assignment_manager.active_assignments:
                            if payload.get("taxi_state") == "bersama penumpang":
                                base_id = self.assignment_manager.active_assignments[taxi_id]["base_id"]
                                self.assignment_manager.cancel_taxi_assignment(taxi_id)
                                
                                sid_fe = self.connected_clients_map_frontend.get(str(taxi_id))
                                if sid_fe:
                                    try:
                                        notification = {
                                            'type': 'cancel_assignment',
                                            'message': f'Your assignment to base {base_id} has been cancelled because another taxi arrived'
                                        }
                                        self.socketio.emit('notification', notification, to=sid_fe)
                                    except Exception as e:
                                        pass
                                def _add_base_back():
                                    try:
                                        return self.data_manager.safely_add_base_request(base_id)
                                    except Exception as e:
                                        return False
                                
                                safe_db_operation(_add_base_back)
                            else:
                                try:
                                    base_id = self.assignment_manager.active_assignments[taxi_id]['base_id']
                                    route = polyline.decode(self.assignment_manager.active_assignments[taxi_id]['polyline'])
                                    
                                    if is_melenceng(taxi_id, route, MELENCENG_RADIUS, self.taxi_current_state):
                                        def _check_taxi_in_base():
                                            try:
                                                for _, base_state in self.base_current_state.items():
                                                    fleet = base_state.get('fleet', [])
                                                    if taxi_id in fleet:
                                                        return True
                                                return False
                                            except Exception as e:
                                                return False

                                        taxi_in_base = safe_db_operation(_check_taxi_in_base)
                                        
                                        if not taxi_in_base:
                                            self.assignment_manager.cancel_taxi_assignment(taxi_id)
                                            
                                            now_wib = datetime.now(ZoneInfo("Asia/Jakarta"))
                                            lat_pelanggaran = payload.get("latitude")
                                            lon_pelanggaran = payload.get("longitude")
                                            current_sim_time = get_current_sim_time()
                                            
                                            def _log_deviation():
                                                try:
                                                    self.log_pelanggaran_data.add_violation(
                                                        timestamp=now_wib,
                                                        taxi_id=taxi_id,
                                                        base_id=base_id,
                                                        reason=f"melenceng pada titik latitude {lat_pelanggaran} dan longitude {lon_pelanggaran} (sim_time: {current_sim_time})"
                                                    )
                                                    sid_fe = self.connected_clients_map_frontend.get(str(taxi_id))
                                                    if(sid_fe):
                                                        notification = {
                                                            'type': 'violation',
                                                            'message': f'Violation detected: Melenceng in assignment to base {base_id}'
                                                        }
                                                        self.socketio.emit('notification', notification, to=sid_fe)
                                                    return True
                                                except Exception as e:
                                                    return False
                                            
                                            safe_db_operation(_log_deviation)
                                            self.assignment_manager.active_assignments.pop(taxi_id, None)
                                except Exception as e:
                                    pass
                                    
                    except Exception as e:
                        logger.error(f"Error processing taxi {taxi_id}: {e}")
                        pass
                time.sleep(5)
            else:
                
                self.normal_mode_active_event.wait(timeout=1)

    def start_taxi_processing_thread(self):
        taxi_thread = threading.Thread(
            target=self.process_data_taxi,   
            name="ProcessDataTaxi",     
            daemon=True                 
        )
        taxi_thread.start()
