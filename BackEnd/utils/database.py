import threading
import time
import psycopg2
from psycopg2.extras import RealDictCursor
import logging
from config.settings import DATABASE_URL

logger = logging.getLogger(__name__)

db_lock = threading.RLock()

def safe_db_operation(operation, *args, max_retries=3, **kwargs):
    for attempt in range(max_retries):
        try:
            with db_lock:
                return operation(*args, **kwargs)
        except psycopg2.Error as e:
            if attempt == max_retries - 1:
                raise
            time.sleep(0.1 * (attempt + 1))
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            time.sleep(0.1 * (attempt + 1))

def debug_lock_status():
    global db_lock
    try:
        acquired = db_lock.acquire(blocking=False)
        if acquired:
            db_lock.release()
            return {"locked": False, "lock_type": "RLock"}
        else:
            return {"locked": True, "lock_type": "RLock"}
    except Exception as e:
        return {"locked": "unknown", "error": str(e), "lock_type": "RLock"}

def get_db_connection():
    print("90")
    max_retries = 3
    print("91")
    for attempt in range(max_retries):
        print("92")
        try:
            print("93")
            return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
        except psycopg2.Error as e:
            print(f"error: {e}")
            print("Error detail:", e.pgerror or str(e))
            print("94")
            if attempt == max_retries - 1:
                print("95")
                raise
            print("96")
            time.sleep(0.1 * (attempt + 1))

def reset_db_lock():
    global db_lock
    db_lock = threading.RLock()
    return debug_lock_status()
