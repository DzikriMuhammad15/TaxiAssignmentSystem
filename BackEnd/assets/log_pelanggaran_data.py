import threading
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Union

class LogPelanggaranDB:
    def __init__(self, dsn: str):
        self._conn = psycopg2.connect(dsn, cursor_factory=RealDictCursor)
        self._lock = threading.Lock()
        self._ensure_table()

    def _ensure_table(self) -> None:
        with self._conn:
            with self._conn.cursor() as cur:
                cur.execute("""
                CREATE TABLE IF NOT EXISTS log_pelanggaran (
                    id SERIAL PRIMARY KEY,
                    timestamp TIMESTAMPTZ NOT NULL,
                    taxi_id TEXT REFERENCES taxi(taxi_id) ON DELETE CASCADE,
                    base_id TEXT REFERENCES base(base_id) ON DELETE CASCADE,
                    reason TEXT
                );
                
                -- Create index on timestamp for better query performance
                CREATE INDEX IF NOT EXISTS idx_log_pelanggaran_timestamp 
                ON log_pelanggaran(timestamp);
                """)

    def __getitem__(self, timestamp: datetime) -> List[Dict[str, Any]]:
        """Get all violation records for a specific timestamp"""
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT id, taxi_id, base_id, reason FROM log_pelanggaran WHERE timestamp = %s ORDER BY id", 
                (timestamp,)
            )
            rows = cur.fetchall()
            if not rows:
                raise KeyError(f"Timestamp '{timestamp}' tidak ditemukan")
            
            return [
                {
                    'id': row['id'],
                    'taxi_id': row['taxi_id'],
                    'base_id': row['base_id'],
                    'reason': row['reason']
                }
                for row in rows
            ]

    def get(self, timestamp: datetime, default=None) -> Union[List[Dict[str, Any]], Any]:
        """Get all violation records for a specific timestamp, return default if not found"""
        try:
            return self.__getitem__(timestamp)
        except KeyError:
            return default

    def get_by_id(self, record_id: int) -> Optional[Dict[str, Any]]:
        """Get a specific violation record by its ID"""
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT id, timestamp, taxi_id, base_id, reason FROM log_pelanggaran WHERE id = %s", 
                (record_id,)
            )
            row = cur.fetchone()
            if not row:
                return None
            
            return {
                'id': row['id'],
                'timestamp': row['timestamp'],
                'taxi_id': row['taxi_id'],
                'base_id': row['base_id'],
                'reason': row['reason']
            }

    def __setitem__(self, timestamp: datetime, data: Dict[str, Any]) -> int:
        """Insert a new violation record and return its ID"""
        with self._lock:
            with self._conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO log_pelanggaran (timestamp, taxi_id, base_id, reason)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id;
                    """,
                    (timestamp, data['taxi_id'], data['base_id'], data['reason'])
                )
                record_id = cur.fetchone()['id']
            self._conn.commit()
            return record_id

    def add_violation(self, timestamp: datetime, taxi_id: str, base_id: str, reason: str) -> int:
        """Add a new violation record and return its ID"""
        data = {
            'taxi_id': taxi_id,
            'base_id': base_id,
            'reason': reason
        }
        return self.__setitem__(timestamp, data)

    def update_violation(self, record_id: int, **kwargs) -> bool:
        """Update a specific violation record by ID"""
        if not kwargs:
            return False
            
        
        set_clauses = []
        values = []
        
        allowed_fields = ['timestamp', 'taxi_id', 'base_id', 'reason']
        for field, value in kwargs.items():
            if field in allowed_fields:
                set_clauses.append(f"{field} = %s")
                values.append(value)
        
        if not set_clauses:
            return False
            
        values.append(record_id)
        
        with self._lock:
            with self._conn.cursor() as cur:
                cur.execute(
                    f"UPDATE log_pelanggaran SET {', '.join(set_clauses)} WHERE id = %s",
                    values
                )
                updated = cur.rowcount > 0
            self._conn.commit()
            return updated

    def delete_violation(self, record_id: int) -> bool:
        """Delete a specific violation record by ID"""
        with self._lock:
            with self._conn.cursor() as cur:
                cur.execute("DELETE FROM log_pelanggaran WHERE id = %s", (record_id,))
                deleted = cur.rowcount > 0
            self._conn.commit()
            return deleted

    def pop(self, timestamp: datetime, default=None) -> Union[List[Dict[str, Any]], Any]:
        """Remove and return all violation records for a specific timestamp"""
        old_records = self.get(timestamp, default)
        if old_records is not default:
            with self._lock:
                with self._conn.cursor() as cur:
                    cur.execute("DELETE FROM log_pelanggaran WHERE timestamp = %s", (timestamp,))
                self._conn.commit()
        return old_records

    def pop_by_id(self, record_id: int) -> Optional[Dict[str, Any]]:
        """Remove and return a specific violation record by ID"""
        old_record = self.get_by_id(record_id)
        if old_record:
            self.delete_violation(record_id)
        return old_record

    def items(self):
        """Iterate over all violation records grouped by timestamp"""
        with self._conn.cursor() as cur:
            cur.execute("""
                SELECT timestamp, 
                       array_agg(
                           json_build_object(
                               'id', id,
                               'taxi_id', taxi_id,
                               'base_id', base_id,
                               'reason', reason
                           ) ORDER BY id
                       ) as records
                FROM log_pelanggaran 
                GROUP BY timestamp 
                ORDER BY timestamp
            """)
            
            for row in cur.fetchall():
                yield row['timestamp'], row['records']

    def all_violations(self):
        """Iterate over all individual violation records"""
        with self._conn.cursor() as cur:
            cur.execute("""
                SELECT id, timestamp, taxi_id, base_id, reason 
                FROM log_pelanggaran 
                ORDER BY timestamp, id
            """)
            
            for row in cur.fetchall():
                yield {
                    'id': row['id'],
                    'timestamp': row['timestamp'],
                    'taxi_id': row['taxi_id'],
                    'base_id': row['base_id'],
                    'reason': row['reason']
                }

    def get_violations_in_range(self, start_time: datetime, end_time: datetime) -> List[Dict[str, Any]]:
        """Get all violation records within a time range"""
        with self._conn.cursor() as cur:
            cur.execute("""
                SELECT id, timestamp, taxi_id, base_id, reason 
                FROM log_pelanggaran 
                WHERE timestamp BETWEEN %s AND %s 
                ORDER BY timestamp, id
            """, (start_time, end_time))
            
            return [
                {
                    'id': row['id'],
                    'timestamp': row['timestamp'],
                    'taxi_id': row['taxi_id'],
                    'base_id': row['base_id'],
                    'reason': row['reason']
                }
                for row in cur.fetchall()
            ]

    def get_violations_by_taxi(self, taxi_id: str) -> List[Dict[str, Any]]:
        """Get all violation records for a specific taxi"""
        with self._conn.cursor() as cur:
            cur.execute("""
                SELECT id, timestamp, taxi_id, base_id, reason 
                FROM log_pelanggaran 
                WHERE taxi_id = %s 
                ORDER BY timestamp, id
            """, (taxi_id,))
            
            return [
                {
                    'id': row['id'],
                    'timestamp': row['timestamp'],
                    'taxi_id': row['taxi_id'],
                    'base_id': row['base_id'],
                    'reason': row['reason']
                }
                for row in cur.fetchall()
            ]

    def get_violations_by_base(self, base_id: str) -> List[Dict[str, Any]]:
        """Get all violation records for a specific base"""
        with self._conn.cursor() as cur:
            cur.execute("""
                SELECT id, timestamp, taxi_id, base_id, reason 
                FROM log_pelanggaran 
                WHERE base_id = %s 
                ORDER BY timestamp, id
            """, (base_id,))
            
            return [
                {
                    'id': row['id'],
                    'timestamp': row['timestamp'],
                    'taxi_id': row['taxi_id'],
                    'base_id': row['base_id'],
                    'reason': row['reason']
                }
                for row in cur.fetchall()
            ]

    def count_violations_by_timestamp(self, timestamp: datetime) -> int:
        """Count how many violation records exist for a specific timestamp"""
        with self._conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) as count FROM log_pelanggaran WHERE timestamp = %s", (timestamp,))
            return cur.fetchone()['count']

    def count_violations_by_taxi(self, taxi_id: str) -> int:
        """Count total violations for a specific taxi"""
        with self._conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) as count FROM log_pelanggaran WHERE taxi_id = %s", (taxi_id,))
            return cur.fetchone()['count']

    def __repr__(self) -> str:
        all_logs = {ts: records for ts, records in self.items()}
        return repr(all_logs)

    def close(self):
        """Close the database connection"""
        if self._conn:
            self._conn.close()


dsn = "postgresql://appuser:secret123@db:5432/taxiAssignmentSystem"
log_pelanggaran_data = LogPelanggaranDB(dsn)
