from multiprocessing import Manager
manager = Manager()
taxi_current_state = manager.dict()
