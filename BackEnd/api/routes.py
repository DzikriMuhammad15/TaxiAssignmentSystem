import jwt
import uuid
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from flask import Blueprint, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from geopy.distance import geodesic
from utils.database import safe_db_operation, get_db_connection, debug_lock_status, reset_db_lock
from utils.simulation_time import get_current_sim_time, simulation_active
from config.settings import SECRET_KEY, BASE_RADIUS
from core.intelligent_agent_manager import IntelligentAgentManager

logger = logging.getLogger(__name__)

def create_api_routes(data_manager, assignment_manager, taxi_current_state, 
                     base_current_state, user_data, connected_clients_operator, 
                     socketio_handler):
    
    api = Blueprint('api', __name__)

    @api.route('/')
    def index():
        return "Backend Server berjalan"

    @api.route("/health", methods=["GET"])
    def health():
        try: 
            
            agent_status = "running" if hasattr(data_manager, 'agent_running') and data_manager.agent_running else "not running"
            
            lock_info = debug_lock_status()
            lock_status = "locked" if lock_info.get("locked") else "available"
            
            db_status = "unknown"
            try:
                def _test_db():
                    try:
                        list(taxi_current_state.items())
                        list(base_current_state.items())
                        return "healthy"
                    except Exception as e:
                        return "unhealthy"
                
                db_status = safe_db_operation(_test_db)
            except Exception as e:
                db_status = f"error: {str(e)}"
            
            return jsonify({
                "status": "ok",
                "agent": agent_status,
                "lock": lock_status,
                "lock_info": lock_info,
                "database": db_status,
                "operators": len(connected_clients_operator),
                "taxis_frontend": len(socketio_handler.connected_clients_map_frontend),
                "active_assignments": len(assignment_manager.active_assignments),
                "current_sim_time": get_current_sim_time(),
                "simulation_active": simulation_active
            }), 200
        except Exception as e:
            return jsonify(status="fail", reason=str(e)), 500

    @api.route("/api/reset_lock", methods=["POST"])
    def reset_lock():
        try:
            old_lock_info = debug_lock_status()
            new_lock_info = reset_db_lock()
            
            return jsonify({
                "status": "success",
                "message": "Lock has been reset",
                "old_lock_info": old_lock_info,
                "new_lock_info": new_lock_info
            }), 200
        except Exception as e:
            return jsonify(status="fail", reason=str(e)), 500

    @api.route('/api/registerDriver', methods=['POST'])
    def api_register_driver():
        try:
            data = request.json or {}
            username = data.get('username')
            name = data.get('name')
            password = data.get('password')
            taxi_id = data.get('taxi_id')
            role = "driver"

            if not all([username, name, password, role]):
                return jsonify({'error': 'Missing fields'}), 400

            def _check_username_exists():
                try:
                    for uid, u in user_data.items():
                        if u.get('username') == username:
                            return True
                    return False
                except Exception as e:
                    logger.error(f"Error checking username {username}: {e}")
                    return False
                    
            username_exists = safe_db_operation(_check_username_exists)
            if username_exists:
                return jsonify({"error": "Username already exists"}), 409

            def _check_taxi():
                try:
                    return taxi_current_state.get(str(taxi_id)) is not None
                except Exception as e:
                    return False
                    
            taxi_exists = safe_db_operation(_check_taxi)
            if not taxi_exists:
                return jsonify({"error": "taxi_id not registered"}), 400

            def _check_taxi_assigned():
                try:
                    for uid, u in user_data.items():
                        if u.get('taxi_id') == taxi_id and u.get('role') == 'driver':
                            return True
                    return False
                except Exception as e:
                    logger.error(f"Error checking taxi assignment {taxi_id}: {e}")
                    return False
                    
            taxi_assigned = safe_db_operation(_check_taxi_assigned)
            if taxi_assigned:
                return jsonify({"error": "Taxi is already assigned to another driver"}), 409

            hashed_pw = generate_password_hash(password)
            user_id = str(uuid.uuid4())

            def _register_user():
                try:
                    user_data[user_id] = {
                        'username': username,
                        'name': name,
                        'password': hashed_pw,
                        'taxi_id': taxi_id,
                        'role': role
                    }
                    return True
                except Exception as e:
                    return False
                    
            if not safe_db_operation(_register_user):
                return jsonify({'error': 'Failed to register user'}), 500
                
            token = jwt.encode({
                'user_id': user_id,
                'exp': datetime.now(ZoneInfo("UTC")) + timedelta(hours=12)
            }, SECRET_KEY, algorithm='HS256')

            return jsonify({'user_id': user_id, 'token': token}), 201
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @api.route('/api/registerOperator', methods=['POST'])
    def api_register_operator():
        try:
            data = request.json or {}
            username = data.get('username')
            name = data.get('name')
            password = data.get('password')
            role = "operator"
            taxi_id = None

            if not all([username, name, password, role]):
                return jsonify({'error': 'Missing fields'}), 400

            def _check_username_exists():
                try:
                    for uid, u in user_data.items():
                        if u.get('username') == username:
                            return True
                    return False
                except Exception as e:
                    logger.error(f"Error checking username {username}: {e}")
                    return False
                    
            username_exists = safe_db_operation(_check_username_exists)
            if username_exists:
                return jsonify({"error": "Username already exists"}), 409

            hashed_pw = generate_password_hash(password)
            user_id = str(uuid.uuid4())

            def _register_operator():
                try:
                    user_data[user_id] = {
                        'username': username,
                        'name': name,
                        'password': hashed_pw,
                        'taxi_id': taxi_id,
                        'role': role
                    }
                    return True
                except Exception as e:
                    return False
                    
            if not safe_db_operation(_register_operator):
                return jsonify({'error': 'Failed to register operator'}), 500
                
            token = jwt.encode({
                'user_id': user_id,
                'exp': datetime.now(ZoneInfo("UTC")) + timedelta(hours=12)
            }, SECRET_KEY, algorithm='HS256')

            return jsonify({'user_id': user_id, 'token': token}), 201
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @api.route('/api/loginDriver', methods=['POST'])
    def api_login_driver():
        try:
            data = request.json or {}
            username = data.get('username')
            password = data.get('password')

            if not all([username, password]):
                return jsonify({'error': 'Missing fields'}), 400

            def _find_user():
                try:
                    for uid, u in user_data.items():
                        if u['username'] == username:
                            return uid, u
                    return None, None
                except Exception as e:
                    return None, None

            user_id, user = safe_db_operation(_find_user)

            if (not user) or (not check_password_hash(user['password'], password)):
                return jsonify({'error': 'Invalid credentials'}), 401
            
            if user["role"] != "driver":
                return jsonify({'error': 'Invalid credentials'}), 401

            token = jwt.encode({
                'user_id': user_id,
                'exp': datetime.now(ZoneInfo("UTC")) + timedelta(hours=12)
            }, SECRET_KEY, algorithm='HS256')

            return jsonify({'message': 'Login successful', 'token': token, 'user_id': user_id}), 200
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @api.route('/api/loginOperator', methods=['POST'])
    def api_login_operator():
        try:
            data = request.json or {}
            username = data.get('username')
            password = data.get('password')

            if not all([username, password]):
                return jsonify({'error': 'Missing fields'}), 400

            def _find_user():
                try:
                    for uid, u in user_data.items():
                        if u['username'] == username:
                            return uid, u
                    return None, None
                except Exception as e:
                    return None, None

            user_id, user = safe_db_operation(_find_user)

            if (not user) or (not check_password_hash(user['password'], password)):
                return jsonify({'error': 'Invalid credentials'}), 401

            if user["role"] != "operator":
                return jsonify({'error': 'Invalid credentials'}), 401

            token = jwt.encode({
                'user_id': user_id,
                'exp': datetime.now(ZoneInfo("UTC")) + timedelta(hours=12)
            }, SECRET_KEY, algorithm='HS256')

            return jsonify({
                'message': 'Login successful', 
                'token': token, 
                'user_id': user_id,
            }), 200
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @api.route('/api/checkInTaxi', methods=['POST'])
    def check_in_taxi():
        try:
            auth_header = request.headers.get('Authorization')
            if not auth_header or not auth_header.startswith('Bearer '):
                return jsonify({'error': 'Authorization header missing or invalid'}), 401
            
            token = auth_header.split(' ')[1]
            payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
            user_id = payload.get('user_id')
            
            def _get_user():
                try:
                    return user_data.get(user_id)
                except Exception as e:
                    return None
                    
            user = safe_db_operation(_get_user)
            if not user or user.get('role') != 'driver':
                return jsonify({'error': 'Unauthorized - must be a driver'}), 403
            
            taxi_id = user.get('taxi_id')
            if not taxi_id or taxi_id is None:
                return jsonify({'error': 'No taxi associated with this driver'}), 400
            
            data = request.json or {}
            base_id = data.get('base_id')
            if not base_id:
                return jsonify({'error': 'base_id is required'}), 400
            
            def _check_base():
                try:
                    return str(base_id) in base_current_state
                except Exception as e:
                    return False
                    
            base_exists = safe_db_operation(_check_base)
            if not base_exists:
                return jsonify({'error': 'Base not found'}), 404
            
            def _get_states():
                try:
                    taxi_state = taxi_current_state.get(str(taxi_id))
                    base_state = base_current_state.get(str(base_id))
                    return taxi_state, base_state
                except Exception as e:
                    return None, None
                    
            taxi_state, base_state = safe_db_operation(_get_states)
            if not taxi_state:
                return jsonify({'error': 'Taxi not found'}), 404
            
            taxi_coord = (taxi_state.get('latitude'), taxi_state.get('longitude'))
            base_coord = (base_state.get('latitude'), base_state.get('longitude'))
            
            distance = geodesic(taxi_coord, base_coord).meters
            if distance > BASE_RADIUS:
                return jsonify({'error': 'Taxi is not in base area', 'distance': distance, 'max_allowed': BASE_RADIUS}), 400
            
            def _check_slot():
                try:
                    return data_manager.availableSlot(base_id)
                except Exception as e:
                    return False
                    
            slot_available = safe_db_operation(_check_slot)
            if not slot_available:
                return jsonify({'error': 'No available slots in this base'}), 400
            
            is_already_in_base = data_manager.is_taxi_in_base_fleet(taxi_id)
            if is_already_in_base:
                return jsonify({'error': 'Taxi is already in base slot'}), 400

            success = data_manager.add_taxi_to_base(taxi_id, base_id)
            if not success:
                return jsonify({'error': 'Failed to add taxi to base'}), 500
            

            for other_taxi_id, assignment in list(assignment_manager.active_assignments.items()):
                if str(other_taxi_id) != str(taxi_id) and assignment.get('base_id') == base_id:
                    assignment_manager.cancel_taxi_assignment(other_taxi_id)
                    
                    # notidikasi
                    sid_fe = socketio_handler.connected_clients_map_frontend.get(str(other_taxi_id))
                    if sid_fe:
                        try:
                            notification = {
                                'type': 'cancel_assignment',
                                'message': f'Your assignment to base {base_id} has been cancelled because another taxi checked in'
                            }
                            socketio_handler.socketio.emit('notification', notification, to=sid_fe)
                        except Exception as e:
                            pass


            socketio_handler.send_operator_update()
            
            return jsonify({'message': f'Taxi {taxi_id} successfully checked in to base {base_id}'}), 200
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Invalid token'}), 401
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @api.route('/api/getActivityBaseLogs', methods=['GET'])
    def get_activity_base_logs():
        try:
            auth_header = request.headers.get('Authorization')
            if not auth_header or not auth_header.startswith('Bearer '):
                return jsonify({'error': 'Authorization header missing or invalid'}), 401
            
            token = auth_header.split(' ')[1]
            payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
            user_id = payload.get('user_id')
            
            def _get_user():
                try:
                    return user_data.get(user_id)
                except Exception as e:
                    return None
                    
            user = safe_db_operation(_get_user)
            if not user or user.get('role') != 'operator':
                return jsonify({'error': 'Unauthorized - must be an operator'}), 403
            
            base_id = request.args.get('base_id')
            start_time_str = request.args.get('start_time')
            end_time_str = request.args.get('end_time')
            
            start_time = None
            end_time = None
            
            if start_time_str:
                try:
                    start_time = datetime.fromisoformat(start_time_str)
                except ValueError:
                    return jsonify({'error': 'Invalid start_time format. Use ISO format (YYYY-MM-DDTHH:MM:SS)'}), 400
                    
            if end_time_str:
                try:
                    end_time = datetime.fromisoformat(end_time_str)
                except ValueError:
                    return jsonify({'error': 'Invalid end_time format. Use ISO format (YYYY-MM-DDTHH:MM:SS)'}), 400
            
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    with get_db_connection() as conn:
                        with conn.cursor() as cur:
                            query = "SELECT timestamp, base_id, status, taxi_id FROM log_base_activity WHERE 1=1"
                            params = []
                            
                            if base_id:
                                query += " AND base_id = %s"
                                params.append(base_id)
                            
                            if start_time:
                                query += " AND timestamp >= %s"
                                params.append(start_time)
                            
                            if end_time:
                                query += " AND timestamp <= %s"
                                params.append(end_time)
                            
                            query += " ORDER BY timestamp DESC"
                            
                            cur.execute(query, params)
                            logs = cur.fetchall()
                            
                            result = []
                            for log in logs:
                                log_dict = dict(log)
                                log_dict['timestamp'] = log_dict['timestamp'].isoformat()
                                result.append(log_dict)
                            
                            return jsonify(result), 200
                except Exception as e:
                    if attempt == max_retries - 1:
                        return jsonify({'error': 'Database error after multiple retries'}), 500
                    time.sleep(0.1 * (attempt + 1))
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @api.route('/api/getLogPelanggaran', methods=['GET'])
    def get_log_pelanggaran():
        try:
            print("1")
            auth_header = request.headers.get('Authorization')
            if not auth_header or not auth_header.startswith('Bearer '):
                print("3")
                return jsonify({'error': 'Authorization header missing or invalid'}), 401
            
            print("4")
            token = auth_header.split(' ')[1]
            print("5")
            payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
            print("6")
            user_id = payload.get('user_id')
            print("7")
            
            def _get_user():
                try:
                    return user_data.get(user_id)
                except Exception as e:
                    return None
            print("8")  
            user = safe_db_operation(_get_user)
            print("9")  
            if not user or user.get('role') != 'operator':
                print("10")  
                return jsonify({'error': 'Unauthorized - must be an operator'}), 403
            
            print("11")  
            taxi_id = request.args.get('taxi_id')
            print("12")  
            start_time_str = request.args.get('start_time')
            print("13")  
            end_time_str = request.args.get('end_time')
            print("14")  
            
            start_time = None
            print("15")  
            end_time = None
            print("16")  
            
            if start_time_str:
                print("17")  
                try:
                    print("18")  
                    start_time = datetime.fromisoformat(start_time_str)
                    print("19")  
                except ValueError:
                    return jsonify({'error': 'Invalid start_time format. Use ISO format (YYYY-MM-DDTHH:MM:SS)'}), 400
                    
            print("20")  
            if end_time_str:
                print("21")  
                try:
                    print("22")  
                    end_time = datetime.fromisoformat(end_time_str)
                    print("23")  
                except ValueError:
                    print("24")  
                    return jsonify({'error': 'Invalid end_time format. Use ISO format (YYYY-MM-DDTHH:MM:SS)'}), 400
            
            print("25")  
            max_retries = 3
            print("26")  
            for attempt in range(max_retries):
                print("27")  
                try:
                    print("28")  
                    with get_db_connection() as conn:
                        print("29")  
                        with conn.cursor() as cur:
                            print("30")  
                            query = "SELECT timestamp, taxi_id, base_id, reason FROM log_pelanggaran WHERE 1=1"
                            print("31")  
                            params = []
                            print("32")  
                            
                            if taxi_id:
                                print("33")  
                                query += " AND taxi_id = %s"
                                print("34")  
                                params.append(taxi_id)
                                print("35")  
                            
                            if start_time:
                                print("36")  
                                query += " AND timestamp >= %s"
                                print("37")  
                                params.append(start_time)
                                print("38")  
                            
                            if end_time:
                                print("39")  
                                query += " AND timestamp <= %s"
                                print("40")  
                                params.append(end_time)
                                print("41")  
                            
                            print("42")  
                            query += " ORDER BY timestamp DESC"
                            print("43")  
                            
                            cur.execute(query, params)
                            print("44")  
                            logs = cur.fetchall()
                            print("45")  
                            
                            result = []
                            print("46")  
                            for log in logs:
                                print("47")  
                                log_dict = dict(log)
                                print("48")  
                                log_dict['timestamp'] = log_dict['timestamp'].isoformat()
                                print("49")  
                                result.append(log_dict)
                                print("50")  
                              
                            return jsonify(result), 200
                except Exception as e:
                    if attempt == max_retries - 1:
                        return jsonify({'error': 'Database error after multiple retries'}), 500
                    time.sleep(0.1 * (attempt + 1))
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    return api
