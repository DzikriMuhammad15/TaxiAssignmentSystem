import threading
import time
import polyline
from datetime import datetime
from zoneinfo import ZoneInfo
from utils.simulation_time import get_current_sim_time
from utils.geo_utils import is_melenceng
from utils.api_client import get_travel_duration
from utils.database import safe_db_operation
import logging

logger = logging.getLogger(__name__)

class AssignmentManager:
    def __init__(self, taxi_current_state, base_current_state, log_pelanggaran_data, 
                 connected_clients_map_frontend, socketio):
        self.taxi_current_state = taxi_current_state
        self.base_current_state = base_current_state
        self.log_pelanggaran_data = log_pelanggaran_data
        self.connected_clients_map_frontend = connected_clients_map_frontend
        self.socketio = socketio
        self.active_assignments = {}
        self.assignment_map = {}

    def get_serializable_assignments(self):
        result = {}
        try:
            for taxi_id, assignment in self.active_assignments.items():
                serializable_assignment = {
                    'base_id': assignment.get('base_id'),
                    'polyline': assignment.get('polyline'),
                    'start_sim_time': assignment.get('start_sim_time'),
                    'timeout_sim_time': assignment.get('timeout_sim_time')
                }
                result[taxi_id] = serializable_assignment
        except Exception as e:
            pass
        return result

    def cancel_taxi_assignment(self, taxi_id):
        try:
            if taxi_id in self.active_assignments:
                assignment = self.active_assignments.get(taxi_id, {})
                
                try:
                    if 'timeout_thread' in assignment and assignment['timeout_thread']:
                        if 'timeout_stop_event' in assignment:
                            assignment['timeout_stop_event'].set()
                except Exception as e:
                    pass
                
                try:
                    if 'deviate_thread' in assignment and assignment['deviate_thread']:
                        if 'deviate_stop_event' in assignment:
                            assignment['deviate_stop_event'].set()
                except Exception as e:
                    pass
                
                self.active_assignments.pop(taxi_id, None)
                return True
        except Exception as e:
            pass
        return False

    def cancel_other_taxi_assignments_to_base(self, current_taxi_id, base_id):
        try:
            for taxi_id, assignment in list(self.active_assignments.items()):
                if taxi_id != current_taxi_id and assignment.get('base_id') == base_id:
                    self.cancel_taxi_assignment(taxi_id)
                    return True
        except Exception as e:
            pass
        return False

    def is_taxi_assigned_to_base(self, taxi_id, target_base_id):
        try:
            assignment = self.active_assignments.get(taxi_id)
            if assignment and assignment.get('base_id') == target_base_id:
                return True
        except Exception as e:
            pass
        return False

    def _timeout_watcher_thread(self, taxi_id, timeout_sim_duration, stop_event):
        try:
            if not isinstance(timeout_sim_duration, (int, float)) or timeout_sim_duration <= 0:
                timeout_sim_duration = 30 
            
            start_sim_time = get_current_sim_time()
            target_sim_time = start_sim_time + timeout_sim_duration
            
            while get_current_sim_time() < target_sim_time:
                if stop_event.is_set():
                    return
                time.sleep(0.1)
            
            if taxi_id in self.active_assignments and not stop_event.is_set():
                base_id = self.active_assignments[taxi_id]['base_id']
                current_sim_time = get_current_sim_time()
                
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
                    now_wib = datetime.now(ZoneInfo("Asia/Jakarta"))
                    try:
                        def _log_violation():
                            self.log_pelanggaran_data.add_violation(
                                timestamp=now_wib,
                                taxi_id=taxi_id,
                                base_id=base_id,
                                reason=f"Timeout (melewati batas waktu simulasi {timeout_sim_duration}s)"
                            )
                            sid_fe = self.connected_clients_map_frontend.get(str(taxi_id))
                            if(sid_fe):
                                notification = {
                                    'type': 'violation',
                                    'message': f'Violation detected: Timeout in assignment to base {base_id}'
                                }
                                self.socketio.emit('notification', notification, to=sid_fe)
                            return True
                        
                        safe_db_operation(_log_violation)
                    except Exception as e:
                        pass
                    
                self.active_assignments.pop(taxi_id, None)
        except Exception as e:
            if taxi_id in self.active_assignments:
                self.active_assignments.pop(taxi_id, None)

    def _deviate_watcher_thread(self, taxi_id, route, radius, timeout_sim_duration, stop_event):
        try:
            if not isinstance(timeout_sim_duration, (int, float)) or timeout_sim_duration <= 0:
                timeout_sim_duration = 300
        
            start_sim_time = get_current_sim_time()
            target_sim_time = start_sim_time + timeout_sim_duration
            check_interval = 1.0
            
            while get_current_sim_time() < target_sim_time:
                if stop_event.is_set():
                    return  
                
                if taxi_id not in self.active_assignments:
                    break
                
                if is_melenceng(taxi_id, route, radius, self.taxi_current_state):
                    current_sim_time = get_current_sim_time()
                    
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
                        base_id = self.active_assignments[taxi_id]['base_id']
                        
                        def _get_taxi_coords():
                            try:
                                taxi = self.taxi_current_state.get(str(taxi_id), {})
                                return taxi.get('latitude', 0), taxi.get('longitude', 0)
                            except Exception as e:
                                return 0, 0

                        lat, lon = safe_db_operation(_get_taxi_coords)
                        
                        now_wib = datetime.now(ZoneInfo("Asia/Jakarta"))
                        try:
                            def _log_violation():
                                self.log_pelanggaran_data.add_violation(
                                    timestamp=now_wib,
                                    taxi_id=taxi_id,
                                    base_id=base_id,
                                    reason=f"melenceng pada titik latitude {lat} dan longitude {lon} (sim_time: {current_sim_time})"
                                )
                                sid_fe = self.connected_clients_map_frontend.get(str(taxi_id)) 
                                if(sid_fe):
                                    notification = {
                                        'type': 'violation',
                                        'message': f'Violation detected: Melenceng in assignment to base {base_id}'
                                    }
                                    self.socketio.emit('notification', notification, to=sid_fe)
                                return True
                            
                            safe_db_operation(_log_violation)
                        except Exception as e:
                            pass
                    
                    self.active_assignments.pop(taxi_id, None)
                    break
            
                next_check_time = get_current_sim_time() + check_interval
                while get_current_sim_time() < next_check_time:
                    if stop_event.is_set():
                        return
                    time.sleep(0.1)
            
        except Exception as e:
            if taxi_id in self.active_assignments:
                self.active_assignments.pop(taxi_id, None)

    def notice_assignment(self, assignments, radius, travel_duration_margin, api_gmaps_simulation_url):
        for taxi_id, data in assignments.items():
            try:
                base_id = data['base_id']
                poly = data['polyline']
                
                if not poly:
                    continue
                    
                route = polyline.decode(poly)
                
                def _get_states():
                    try:
                        taxi = self.taxi_current_state.get(str(taxi_id), {})
                        base = self.base_current_state.get(str(base_id), {})
                        return taxi, base
                    except Exception as e:
                        return {}, {}

                taxi_state, base_state = safe_db_operation(_get_states)
                
                taxi_coords = (taxi_state.get('latitude', 0), taxi_state.get('longitude', 0))
                base_coords = (base_state.get('latitude', 0), base_state.get('longitude', 0))
                
                duration = get_travel_duration(coordAwal=taxi_coords, coordAkhir=base_coords, 
                                             api_gmaps_simulation_url=api_gmaps_simulation_url)
                if duration is None or not isinstance(duration, (int, float)) or duration <= 0:
                    duration = 30*60
                duration = duration/60

                timeout_sim_duration = duration + travel_duration_margin
                current_sim_time = get_current_sim_time()
                
                try:
                    timeout_stop_event = threading.Event()
                    deviate_stop_event = threading.Event()
                    
                    timeout_thread = threading.Thread(
                        target=self._timeout_watcher_thread, 
                        args=(taxi_id, timeout_sim_duration, timeout_stop_event),
                        daemon=True
                    )
                    deviate_thread = threading.Thread(
                        target=self._deviate_watcher_thread, 
                        args=(taxi_id, route, radius, timeout_sim_duration, deviate_stop_event),
                        daemon=True
                    )
                    
                    timeout_thread.start()
                    deviate_thread.start()
                    
                    self.active_assignments[taxi_id] = {
                        'base_id': base_id,
                        'polyline': poly,
                        'timeout_thread': timeout_thread,
                        'deviate_thread': deviate_thread,
                        'timeout_stop_event': timeout_stop_event,
                        'deviate_stop_event': deviate_stop_event,
                        'start_sim_time': current_sim_time,
                        'timeout_sim_time': current_sim_time + timeout_sim_duration
                    }
                except Exception as e:
                    pass
                    
            except Exception as e:
                pass
