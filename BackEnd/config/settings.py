import os

MQTT_BROKER = "mosquitto"
MQTT_PORT = 1883
TOPIC_GPS = "gps/tracker"
TOPIC_BASE_REQUEST = "request/base"
TOPIC_BASE_CHANGE = "state/base"
TOPIC_BASE_REGISTER = "register/base"
TOPIC_TAXI_ASSIGNMENT = "assignment/taxi"


TOPIC_ASSIGNMENT_REQUEST = "taxi/assignment/request"
TOPIC_ASSIGNMENT_RESPONSE = "taxi/assignment/response"
TOPIC_RESET_MQTT = "reset/mqtt"
TOPIC_RECONNECTION_SIGNAL = "server/reconnection/signal"


TRAVEL_DURATION_MARGIN = 15
MELENCENG_RADIUS = 1000
BASE_RADIUS = 500
SECRET_KEY = 'tugasAkhirDzikri'
BATTERY_TRESHOLD = 10
REFERENCE_SET_SIZE = 2
NUM_OF_CYCLE = 10
ALPHA_D = 0.00024524
ALPHA_T = 0
MAX_ITER_GENERATE = 100
EC_PROBE_ITERATION = 5
ALPHA = 1
BETA = 1
GAMMA = 1

API_GMAPS_SIMULATION_URL = "http://gmaps-backend-backend-simulation:5001"
API_ORDER_RATE_SIMULATION_URL = "http://order-rate-backend-simulation-60-bases:5022"

DATABASE_URL = "postgresql://appuser:secret123@db:5432/taxiAssignmentSystem"

JUMLAH_TAXI = 200
BASE_DATA_INIT = [
  # MALL
  {"name": "d'Botanica Pasteur", "latitude": -6.8812, "longitude": 107.5800, "capacity": 3, "order_rate": 12,  "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},
  {"name": "Cihampelas Walk (Ciwalk)", "latitude": -6.8938, "longitude": 107.6052, "capacity": 4, "order_rate": 11,  "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},
  {"name": "Paris Van Java (PVJ)", "latitude": -6.8895, "longitude": 107.5957, "capacity": 4, "order_rate": 15,  "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},
  {"name": "Bandung Indah Plaza (BIP)", "latitude": -6.9112, "longitude": 107.6097, "capacity": 3, "order_rate": 14,  "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},
  {"name": "Summarecon Mall Bandung", "latitude": -6.9600, "longitude": 107.7170, "capacity": 5, "order_rate": 13,  "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},
  {"name": "Trans Studio Mall Bandung", "latitude": -6.9276, "longitude": 107.6364, "capacity": 5, "order_rate": 20,  "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},

  # MODA TRANSPORTASI
  {"name": "Stasiun Bandung", "latitude": -6.9175, "longitude": 107.6030, "capacity": 4, "order_rate": 18,  "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},
  {"name": "Stasiun Padalarang Whoosh", "latitude": -6.8375, "longitude": 107.4708, "capacity": 2, "order_rate": 6,  "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},
  {"name": "Stasiun Tegalluar Whoosh", "latitude": -6.9850, "longitude": 107.7400, "capacity": 2, "order_rate": 7,  "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},
  {"name": "Terminal Leuwipanjang", "latitude": -6.9333, "longitude": 107.5742, "capacity": 3, "order_rate": 10,  "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},
  {"name": "Kertajati Internasional Airport", "latitude": -6.5569, "longitude": 108.2314, "capacity": 6, "order_rate": 5,  "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},
  {"name": "Cititrans Dipatiukur", "latitude": -6.8840, "longitude": 107.6186, "capacity": 2, "order_rate": 9,  "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},
  {"name": "Shuttle Drop Off Pasteur", "latitude": -6.8855, "longitude": 107.5779, "capacity": 3, "order_rate": 8,  "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},

  # RESIDENSIAL
  {"name": "Majesty Apartement", "latitude": -6.8858, "longitude": 107.5790, "capacity": 2, "order_rate": 6,  "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},
  {"name": "Kota Baru Parahyangan", "latitude": -6.8655, "longitude": 107.4750, "capacity": 3, "order_rate": 7,  "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},

  # TEMPAT HIBURAN MALAM
  {"name": "W Super Club", "latitude": -6.9180, "longitude": 107.6150, "capacity": 2, "order_rate": 9,  "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},
  {"name": "MOD Pool and Club", "latitude": -6.9205, "longitude": 107.6162, "capacity": 2, "order_rate": 10,  "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},

  # LEASURE PARK
  {"name": "Dusun Bambu", "latitude": -6.7904, "longitude": 107.5950, "capacity": 2, "order_rate": 7,  "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},
  {"name": "Lembang Park Zoo", "latitude": -6.8247, "longitude": 107.6133, "capacity": 2, "order_rate": 6,  "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},
  {"name": "The Lodge Maribaya", "latitude": -6.8012, "longitude": 107.6857, "capacity": 2, "order_rate": 5,  "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},

  # GOVERNMENT
  {"name": "Komplek Pemerintahan Kab. Bandung (Soreang)", "latitude": -7.0223, "longitude": 107.5186, "capacity": 3, "order_rate": 8,  "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50},

  # OTHER
  {"name": "Rest Area Alun-Alun Lembang", "latitude": -6.8180, "longitude": 107.6169, "capacity": 2, "order_rate": 4,  "mean_order_rate": 10, "std_order_rate": 1, "min_order_rate": 0, "max_order_rate": 50}
]
