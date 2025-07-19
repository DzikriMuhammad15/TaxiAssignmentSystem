import eventlet
eventlet.monkey_patch()

import logging
import threading
from flask import Flask
from flask_socketio import SocketIO
from flask_cors import CORS


from config.settings import *


from utils.database import safe_db_operation
from utils.simulation_time import get_current_sim_time


from core.data_manager import DataManager
from core.assignment_manager import AssignmentManager
from core.intelligent_agent_manager import IntelligentAgentManager


from handlers.mqtt_handler import MQTTHandler
from handlers.socketio_handler import SocketIOHandler
from handlers.taxi_processor import TaxiProcessor


from api.routes import create_api_routes


from assets import intelligent_agent_prec_independent_optimized as intelligent_agent
from assets.base_data import base_current_state
from assets.base_request_data import base_request_data_now
from assets.taxi_data import taxi_current_state
from assets.log_pelanggaran_data import log_pelanggaran_data
from assets.log_base_activity_data import log_base_activity
from assets.users_data import user_data
from assets.taxi_reference_data import taxi_reference_data
from assets.base_reference_data import base_reference_data


logging.basicConfig(level=logging.INFO, 
                 format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class TaxiAssignmentServer:
    def __init__(self):
        """
        inisialisasi seluruh komponen sistem
        """
        self.app = Flask(__name__)
        self.app.config['SECRET_KEY'] = SECRET_KEY
        CORS(self.app, resources={r"/api/*": {"origins": "*"}}, supports_credentials=True)
        self.socketio = SocketIO(self.app, cors_allowed_origins="*", async_mode='eventlet')
        
        
        self.normal_mode_active_event = threading.Event()
        self.simulation_mode_active_event = threading.Event()
        self.normal_mode_active_event.set() 
        self.simulation_mode_active_event.clear()
        
        self.connected_clients_map_frontend = {}
        self.connected_clients_operator = []
        self.in_base_area_map = {}
        
        
        self.data_manager = DataManager(
            base_current_state, taxi_current_state, base_request_data_now,
            base_reference_data, taxi_reference_data, log_base_activity
        )
        
        self.assignment_manager = AssignmentManager(
            taxi_current_state, base_current_state, log_pelanggaran_data,
            self.connected_clients_map_frontend, self.socketio
        )
        
        
        try:
            self.intelligent_agent = intelligent_agent.PathRelinkingEjectionChain(
                battery_treshold=BATTERY_TRESHOLD, 
                reference_set_size=REFERENCE_SET_SIZE, 
                alpha_d=ALPHA_D, 
                alpha_t=ALPHA_T, 
                max_iter_generate=MAX_ITER_GENERATE,
                alpha=ALPHA,
                beta=BETA,
                gamma=GAMMA
            )
        except Exception as e:
            logger.error(f"Error initializing PREC agent: {e}")
            self.intelligent_agent = None
        
        self.agent_manager = IntelligentAgentManager(
            self.intelligent_agent, self.data_manager, self.assignment_manager,
            taxi_current_state, base_current_state, base_request_data_now,
            None, self.connected_clients_map_frontend, self.socketio,
            self.normal_mode_active_event 
        )
             
        self.socketio_handler = SocketIOHandler(
            self.socketio, taxi_current_state, base_current_state,
            self.assignment_manager, base_request_data_now, 
            self.connected_clients_map_frontend, self.connected_clients_operator,
            self.normal_mode_active_event 
        )

        self.mqtt_handler = MQTTHandler(
            self.data_manager, self.assignment_manager, taxi_current_state,
            base_current_state, log_base_activity, self.in_base_area_map,
            self.connected_clients_map_frontend, self.socketio,
            self.intelligent_agent, 
            self.normal_mode_active_event, 
            self.simulation_mode_active_event,
            self.socketio_handler
        )

        self.agent_manager.mqtt_handler = self.mqtt_handler
        
        self.taxi_processor = TaxiProcessor(
            self.data_manager, self.assignment_manager, taxi_current_state,
            base_current_state, log_base_activity, log_pelanggaran_data,
            self.connected_clients_map_frontend, self.socketio, self.in_base_area_map,
            self.normal_mode_active_event 
        )
        
        
        self.socketio_handler.register_handlers()
        
        
        api_routes = create_api_routes(
            self.data_manager, self.assignment_manager, taxi_current_state,
            base_current_state, user_data, self.connected_clients_operator,
            self.socketio_handler
        )
        self.app.register_blueprint(api_routes)

    def initialize_data(self):
        """
        inisiallisasi data base dan taxi
        """
        try:
            if not self.data_manager.init_data(base_data_init=BASE_DATA_INIT, jumlah_taxi=JUMLAH_TAXI):
                logger.error("Failed to initialize data, but continuing...")
            else:
                logger.info("Data initialization completed successfully")
        except Exception as e:
            logger.error(f"Error during data initialization: {e}")

    def start_background_threads(self):
        """
        menjalankan thread: mqtt, socketio, intelligent agent
        """
        try:
            
            logger.info("Starting MQTT thread...")
            mqtt_thread = threading.Thread(target=self.mqtt_handler.start_mqtt_thread, daemon=True)
            mqtt_thread.start()
            
            
            logger.info("Starting taxi processing thread...")
            self.taxi_processor.start_taxi_processing_thread()
            
            
            logger.info("Starting operator update thread...")
            self.socketio_handler.start_operator_update_thread()
            
            
            logger.info("Starting periodic intelligent agent...")
            self.agent_manager.start_periodic_agent()
            
        except Exception as e:
            logger.error(f"Error starting background threads: {e}")

    def run(self, host='0.0.0.0', port=5010, debug=False):
        """
        menjalankan server
        """
        try:
            logger.info("Initializing taxi assignment system...")
            
            
            self.initialize_data()
            
            
            self.start_background_threads()
            
            logger.info(f"Server starting on {host}:{port}")
            self.socketio.run(self.app, host=host, port=port, debug=debug)
            
        except Exception as e:
            logger.error(f"Error starting server: {e}")
        finally:
            logger.info("Shutting down server...")
            self.agent_manager.stop_periodic_agent()

def main():
    server = TaxiAssignmentServer()
    server.run()

if __name__ == '__main__':
    main()
