import psycopg2
from psycopg2.extras import RealDictCursor
import threading

class BaseRequestList:
    def __init__(self, dsn):
        self._conn = psycopg2.connect(dsn, cursor_factory=RealDictCursor)
        self._lock = threading.Lock()
        self._ensure_table()

    def _ensure_table(self):
        with self._conn:
            with self._conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS base_request_data_now (
                        id SERIAL PRIMARY KEY,
                        base_id TEXT NOT NULL
                    );
                """)

    def append(self, base_id):
        with self._lock:
            with self._conn.cursor() as cur:
                cur.execute("INSERT INTO base_request_data_now (base_id) VALUES (%s);", (base_id,))
            self._conn.commit()

    def pop(self, index=-1):
        with self._lock:
            with self._conn.cursor() as cur:
                cur.execute("SELECT id, base_id FROM base_request_data_now ORDER BY id;")
                rows = cur.fetchall()
                if not rows:
                    raise IndexError("pop from empty list")
                if index < 0:
                    index += len(rows)
                if index < 0 or index >= len(rows):
                    raise IndexError("pop index out of range")
                row = rows[index]
                cur.execute("DELETE FROM base_request_data_now WHERE id = %s;", (row['id'],))
            self._conn.commit()
            return row['base_id']

    def __getitem__(self, index):
        with self._conn.cursor() as cur:
            cur.execute("SELECT base_id FROM base_request_data_now ORDER BY id;")
            rows = cur.fetchall()
            if index < 0:
                index += len(rows)
            if index < 0 or index >= len(rows):
                raise IndexError("list index out of range")
            return rows[index]['base_id']

    def __len__(self):
        with self._conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM base_request_data_now;")
            result = cur.fetchone()
            if result and 'count' in result:
                return result['count']
            return 0

    def __iter__(self):
        with self._conn.cursor() as cur:
            cur.execute("SELECT base_id FROM base_request_data_now ORDER BY id;")
            rows = cur.fetchall()
            for row in rows:
                yield row['base_id']

    def clear(self):
        with self._lock:
            with self._conn.cursor() as cur:
                cur.execute("DELETE FROM base_request_data_now;")
            self._conn.commit()

    def __repr__(self):
        return repr(list(self))
    
    def remove(self, base_id):
        with self._lock:
            with self._conn.cursor() as cur:
                cur.execute("""
                    SELECT id
                      FROM base_request_data_now
                     WHERE base_id = %s
                     ORDER BY id
                     LIMIT 1;
                """, (base_id,))
                result = cur.fetchone()
                if not result:
                    raise ValueError(f"base_id '{base_id}' tidak ditemukan")
                target_id = result['id']

                
                cur.execute("""
                    DELETE FROM base_request_data_now
                     WHERE id = %s;
                """, (target_id,))

            
            self._conn.commit()

dsn = "postgresql://appuser:secret123@db:5432/taxiAssignmentSystem"
base_request_data_now = BaseRequestList(dsn)