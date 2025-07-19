from multiprocessing import Manager
manager = Manager()
base_current_state = manager.dict()
