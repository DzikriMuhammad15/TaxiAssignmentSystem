import threading
import psycopg2
from psycopg2.extras import RealDictCursor
import logging

logger = logging.getLogger(__name__)

class BaseDB:
    def __init__(self, dsn: str):
        self._conn = psycopg2.connect(dsn, cursor_factory=RealDictCursor)
        self._lock = threading.Lock()
        self._ensure_table()

    def _ensure_table(self):
        with self._conn:
            with self._conn.cursor() as cur:
                cur.execute("""
                CREATE TABLE IF NOT EXISTS base (
                    base_id TEXT PRIMARY KEY,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                );
                """)

    def __getitem__(self, base_id: str) -> dict:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT base_id, created_at FROM base WHERE base_id=%s",
                (base_id,)
            )
            row = cur.fetchone()
            if not row:
                raise KeyError(f"Base '{base_id}' tidak ditemukan")
            return dict(row)

    def get(self, base_id: str, default=None) -> dict:
        try:
            return self.__getitem__(base_id)
        except KeyError:
            return default

    def __setitem__(self, base_id: str, data: dict):
        with self._lock:
            with self._conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO base(base_id)
                    VALUES(%s)
                    ON CONFLICT(base_id) DO NOTHING;
                    """,
                    (base_id,)
                )
            self._conn.commit()

    def pop(self, base_id: str, default=None) -> dict:
        old = self.get(base_id, default)
        with self._lock:
            with self._conn.cursor() as cur:
                cur.execute("DELETE FROM base WHERE base_id=%s", (base_id,))
            self._conn.commit()
        return old

    def items(self):
        with self._conn.cursor() as cur:
            cur.execute("SELECT base_id, created_at FROM base ORDER BY base_id")
            for row in cur.fetchall():
                yield row['base_id'], {'created_at': row['created_at']}

    def keys(self):
        with self._conn.cursor() as cur:
            cur.execute("SELECT base_id FROM base ORDER BY base_id")
            for row in cur.fetchall():
                yield row['base_id']

    def exists(self, base_id: str) -> bool:
        with self._conn.cursor() as cur:
            cur.execute("SELECT 1 FROM base WHERE base_id = %s", (base_id,))
            return cur.fetchone() is not None

    def add_base(self, base_id: str) -> bool:
        try:
            with self._lock:
                with self._conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO base(base_id) VALUES(%s) ON CONFLICT(base_id) DO NOTHING;",
                        (base_id,)
                    )
                self._conn.commit()
                logger.info(f"Added base {base_id} to reference table")
                return True
        except Exception as e:
            logger.error(f"Error adding base {base_id}: {e}")
            return False

    def remove_base(self, base_id: str) -> bool:
        try:
            with self._lock:
                with self._conn.cursor() as cur:
                    cur.execute("DELETE FROM base WHERE base_id = %s", (base_id,))
                    deleted_count = cur.rowcount
                self._conn.commit()
                if deleted_count > 0:
                    logger.info(f"Removed base {base_id} from reference table")
                    return True
                else:
                    logger.warning(f"Base {base_id} not found for removal")
                    return False
        except Exception as e:
            logger.error(f"Error removing base {base_id}: {e}")
            return False

    def get_all_base_ids(self) -> list:
        with self._conn.cursor() as cur:
            cur.execute("SELECT base_id FROM base ORDER BY base_id")
            return [row['base_id'] for row in cur.fetchall()]

    def __len__(self):
        with self._conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM base")
            result = cur.fetchone()
            return result['count'] if result else 0

    def __repr__(self):
        return repr({base_id: data for base_id, data in self.items()})


dsn = "postgresql://appuser:secret123@db:5432/taxiAssignmentSystem"
base_reference_data = BaseDB(dsn)
