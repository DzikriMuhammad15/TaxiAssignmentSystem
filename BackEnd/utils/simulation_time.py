import threading
import time

current_sim_time = 0.0
sim_time_lock = threading.RLock()
simulation_active = False

def update_sim_time(new_sim_time):
    global current_sim_time, simulation_active
    with sim_time_lock:
        if new_sim_time > current_sim_time:
            current_sim_time = new_sim_time
            simulation_active = True
        elif not simulation_active:
            current_sim_time = new_sim_time
            simulation_active = True

def get_current_sim_time():
    with sim_time_lock:
        return current_sim_time

def sim_time_sleep(duration_seconds):
    if not simulation_active:
        time.sleep(duration_seconds)
        return
    
    start_sim_time = get_current_sim_time()
    target_sim_time = start_sim_time + duration_seconds
    
    while get_current_sim_time() < target_sim_time:
        time.sleep(0.1)
