import threading
import psycopg2
from psycopg2.extras import RealDictCursor
import logging

logger = logging.getLogger(__name__)

class TaxiDB:
    def __init__(self, dsn: str):
        self._conn = psycopg2.connect(dsn, cursor_factory=RealDictCursor)
        self._lock = threading.Lock()
        self._ensure_table()

    def _ensure_table(self):
        with self._conn:
            with self._conn.cursor() as cur:
                cur.execute("""
                CREATE TABLE IF NOT EXISTS taxi (
                    taxi_id TEXT PRIMARY KEY,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                );
                """)

    def __getitem__(self, taxi_id: str) -> dict:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT taxi_id, created_at FROM taxi WHERE taxi_id=%s",
                (taxi_id,)
            )
            row = cur.fetchone()
            if not row:
                raise KeyError(f"Taxi '{taxi_id}' tidak ditemukan")
            return dict(row)

    def get(self, taxi_id: str, default=None) -> dict:
        try:
            return self.__getitem__(taxi_id)
        except KeyError:
            return default

    def __setitem__(self, taxi_id: str, data: dict):
        with self._lock:
            with self._conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO taxi(taxi_id)
                    VALUES(%s)
                    ON CONFLICT(taxi_id) DO NOTHING;
                    """,
                    (taxi_id,)
                )
            self._conn.commit()

    def pop(self, taxi_id: str, default=None) -> dict:
        old = self.get(taxi_id, default)
        with self._lock:
            with self._conn.cursor() as cur:
                cur.execute("DELETE FROM taxi WHERE taxi_id=%s", (taxi_id,))
            self._conn.commit()
        return old

    def items(self):
        with self._conn.cursor() as cur:
            cur.execute("SELECT taxi_id, created_at FROM taxi ORDER BY taxi_id")
            for row in cur.fetchall():
                yield row['taxi_id'], {'created_at': row['created_at']}

    def keys(self):
        with self._conn.cursor() as cur:
            cur.execute("SELECT taxi_id FROM taxi ORDER BY taxi_id")
            for row in cur.fetchall():
                yield row['taxi_id']

    def exists(self, taxi_id: str) -> bool:
        with self._conn.cursor() as cur:
            cur.execute("SELECT 1 FROM taxi WHERE taxi_id = %s", (taxi_id,))
            return cur.fetchone() is not None

    def add_taxi(self, taxi_id: str) -> bool:
        try:
            with self._lock:
                with self._conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO taxi(taxi_id) VALUES(%s) ON CONFLICT(taxi_id) DO NOTHING;",
                        (taxi_id,)
                    )
                self._conn.commit()
                logger.info(f"Added taxi {taxi_id} to reference table")
                return True
        except Exception as e:
            logger.error(f"Error adding taxi {taxi_id}: {e}")
            return False

    def remove_taxi(self, taxi_id: str) -> bool:
        try:
            with self._lock:
                with self._conn.cursor() as cur:
                    cur.execute("DELETE FROM taxi WHERE taxi_id = %s", (taxi_id,))
                    deleted_count = cur.rowcount
                self._conn.commit()
                if deleted_count > 0:
                    logger.info(f"Removed taxi {taxi_id} from reference table")
                    return True
                else:
                    logger.warning(f"Taxi {taxi_id} not found for removal")
                    return False
        except Exception as e:
            logger.error(f"Error removing taxi {taxi_id}: {e}")
            return False

    def get_all_taxi_ids(self) -> list:
        with self._conn.cursor() as cur:
            cur.execute("SELECT taxi_id FROM taxi ORDER BY taxi_id")
            return [row['taxi_id'] for row in cur.fetchall()]

    def __len__(self):
        with self._conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM taxi")
            result = cur.fetchone()
            return result['count'] if result else 0

    def __repr__(self):
        return repr({taxi_id: data for taxi_id, data in self.items()})


dsn = "postgresql://appuser:secret123@db:5432/taxiAssignmentSystem"
taxi_reference_data = TaxiDB(dsn)
