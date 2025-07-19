import logging
from flask import request
from utils.simulation_time import get_current_sim_time, simulation_active
from utils.database import safe_db_operation
import threading
import time


logger = logging.getLogger(__name__)

class SocketIOHandler:
    def __init__(self, socketio, taxi_current_state, base_current_state, 
                 assignment_manager, base_request_data_now, connected_clients_map_frontend, 
                 connected_clients_operator, normal_mode_active_event):
        self.socketio = socketio
        self.taxi_current_state = taxi_current_state
        self.base_current_state = base_current_state
        self.assignment_manager = assignment_manager
        self.base_request_data_now = base_request_data_now
        self.connected_clients_map_frontend = connected_clients_map_frontend
        self.connected_clients_operator = connected_clients_operator
        self.normal_mode_active_event = normal_mode_active_event

    def register_handlers(self):
        self.socketio.on_event('connect', self.handle_connect)
        self.socketio.on_event('frontend_register', self.handle_frontend_register)
        self.socketio.on_event('operator_register', self.handle_operator_register)

    def handle_connect(self):
        try:
            logger.info(f"Client connected: {request.sid}")
            self.socketio.send("Selamat datang di server SocketIO!", to=request.sid)
        except Exception as e:
            logger.error(f"Error in handle_connect: {e}")

    def handle_frontend_register(self, data):
        try:
            taxi_id = data.get('taxi_id')
            self.connected_clients_map_frontend[str(taxi_id)] = request.sid
            logger.info(f"Frontend registered for taxi {taxi_id} with sid {request.sid}")
            print(f"DEBUG: Current connected clients: {self.connected_clients_map_frontend}")
        except Exception as e:
            logger.error(f"Error in handle_frontend_register: {e}")

    def handle_operator_register(self):
        try:
            if request.sid not in self.connected_clients_operator:
                self.connected_clients_operator.append(request.sid)
                logger.info(f"Operator registered with sid: {request.sid}")
            
            def _get_initial_data():
                try:
                    return {
                        'taxi_states': dict(self.taxi_current_state.items()),
                        'base_states': dict(self.base_current_state.items()),
                        'active_assignments': self.assignment_manager.get_serializable_assignments(),
                        'base_requests': list(self.base_request_data_now),
                        'current_sim_time': get_current_sim_time(),
                        'simulation_active': simulation_active
                    }
                except Exception as e:
                    return {
                        'taxi_states': {},
                        'base_states': {},
                        'active_assignments': {},
                        'base_requests': [],
                        'current_sim_time': 0,
                        'simulation_active': False
                    }

            initial_data = safe_db_operation(_get_initial_data)
            self.socketio.emit('initial_data', initial_data, to=request.sid)
            
        except Exception as e:
            logger.error(f"Error in handle_operator_register: {e}")

    def send_operator_update(self):
        try:
            def _get_update_data():
                try:
                    return {
                        'taxi_states': dict(self.taxi_current_state.items()),
                        'base_states': dict(self.base_current_state.items()),
                        'active_assignments': self.assignment_manager.get_serializable_assignments(),
                        'base_requests': list(self.base_request_data_now),
                        'current_sim_time': get_current_sim_time(),
                        'simulation_active': simulation_active
                    }
                except Exception as e:
                    return {
                        'taxi_states': {},
                        'base_states': {},
                        'active_assignments': {},
                        'base_requests': [],
                        'current_sim_time': 0,
                        'simulation_active': False
                    }

            update_data = safe_db_operation(_get_update_data)
            
            for operator_sid in self.connected_clients_operator[:]:  
                try:
                    self.socketio.emit('update_data', update_data, to=operator_sid)
                except Exception as e:
                    try:
                        self.connected_clients_operator.remove(operator_sid)
                    except ValueError:
                        pass
                        
        except Exception as e:
            logger.error(f"Error in send_operator_update: {e}")

    def start_operator_update_thread(self):
        
        def operator_update_thread():
            while True:
                
                if self.normal_mode_active_event.is_set():
                    try:
                        self.send_operator_update()
                    except Exception as e:
                        pass
                    time.sleep(1)
                else:
                    
                    self.normal_mode_active_event.wait(timeout=1)

        update_thread = threading.Thread(target=operator_update_thread, daemon=True)
        update_thread.start()
