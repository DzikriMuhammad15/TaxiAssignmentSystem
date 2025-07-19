import threading
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import List, Dict, Any, Optional, Union

class LogBaseActivityDB:
    def __init__(self, dsn: str):
        self._conn = psycopg2.connect(dsn, cursor_factory=RealDictCursor)
        self._lock = threading.Lock()
        self._ensure_table()

    def _ensure_table(self) -> None:
        with self._conn:
            with self._conn.cursor() as cur:
                cur.execute("""
                CREATE TABLE IF NOT EXISTS log_base_activity (
                    id SERIAL PRIMARY KEY,
                    timestamp TIMESTAMPTZ NOT NULL,
                    base_id TEXT REFERENCES base(base_id) ON DELETE CASCADE,
                    status TEXT,
                    taxi_id TEXT REFERENCES taxi(taxi_id) ON DELETE CASCADE,
                    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                );
                
                -- Create index on timestamp for better query performance
                CREATE INDEX IF NOT EXISTS idx_log_base_activity_timestamp 
                ON log_base_activity(timestamp);
                """)

    def __getitem__(self, timestamp: datetime) -> List[Dict[str, Any]]:
        """Get all records for a specific timestamp"""
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT id, base_id, status, taxi_id, created_at FROM log_base_activity WHERE timestamp = %s ORDER BY id", 
                (timestamp,)
            )
            rows = cur.fetchall()
            if not rows:
                raise KeyError(f"Timestamp '{timestamp}' tidak ditemukan")
            
            return [
                {
                    'id': row['id'],
                    'base_id': row['base_id'],
                    'status': row['status'],
                    'taxi_id': row['taxi_id'],
                    'created_at': row['created_at']
                }
                for row in rows
            ]

    def get(self, timestamp: datetime, default=None) -> Union[List[Dict[str, Any]], Any]:
        """Get all records for a specific timestamp, return default if not found"""
        try:
            return self.__getitem__(timestamp)
        except KeyError:
            return default

    def get_by_id(self, record_id: int) -> Optional[Dict[str, Any]]:
        """Get a specific record by its ID"""
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT id, timestamp, base_id, status, taxi_id, created_at FROM log_base_activity WHERE id = %s", 
                (record_id,)
            )
            row = cur.fetchone()
            if not row:
                return None
            
            return {
                'id': row['id'],
                'timestamp': row['timestamp'],
                'base_id': row['base_id'],
                'status': row['status'],
                'taxi_id': row['taxi_id'],
                'created_at': row['created_at']
            }

    def __setitem__(self, timestamp: datetime, data: Dict[str, Any]) -> int:
        """Insert a new record and return its ID"""
        with self._lock:
            with self._conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO log_base_activity (timestamp, base_id, status, taxi_id)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id;
                    """,
                    (timestamp, data['base_id'], data['status'], data['taxi_id'])
                )
                record_id = cur.fetchone()['id']
            self._conn.commit()
            return record_id

    def add_record(self, timestamp: datetime, base_id: str, status: str, taxi_id: str) -> int:
        """Add a new record and return its ID"""
        data = {
            'base_id': base_id,
            'status': status,
            'taxi_id': taxi_id
        }
        return self.__setitem__(timestamp, data)

    def update_record(self, record_id: int, **kwargs) -> bool:
        """Update a specific record by ID"""
        if not kwargs:
            return False

        set_clauses = []
        values = []
        
        allowed_fields = ['timestamp', 'base_id', 'status', 'taxi_id']
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
                    f"UPDATE log_base_activity SET {', '.join(set_clauses)} WHERE id = %s",
                    values
                )
                updated = cur.rowcount > 0
            self._conn.commit()
            return updated

    def delete_record(self, record_id: int) -> bool:
        """Delete a specific record by ID"""
        with self._lock:
            with self._conn.cursor() as cur:
                cur.execute("DELETE FROM log_base_activity WHERE id = %s", (record_id,))
                deleted = cur.rowcount > 0
            self._conn.commit()
            return deleted

    def pop(self, timestamp: datetime, default=None) -> Union[List[Dict[str, Any]], Any]:
        """Remove and return all records for a specific timestamp"""
        old_records = self.get(timestamp, default)
        if old_records is not default:
            with self._lock:
                with self._conn.cursor() as cur:
                    cur.execute("DELETE FROM log_base_activity WHERE timestamp = %s", (timestamp,))
                self._conn.commit()
        return old_records

    def pop_by_id(self, record_id: int) -> Optional[Dict[str, Any]]:
        """Remove and return a specific record by ID"""
        old_record = self.get_by_id(record_id)
        if old_record:
            self.delete_record(record_id)
        return old_record

    def items(self):
        """Iterate over all records grouped by timestamp"""
        with self._conn.cursor() as cur:
            cur.execute("""
                SELECT timestamp, 
                       array_agg(
                           json_build_object(
                               'id', id,
                               'base_id', base_id,
                               'status', status,
                               'taxi_id', taxi_id,
                               'created_at', created_at
                           ) ORDER BY id
                       ) as records
                FROM log_base_activity 
                GROUP BY timestamp 
                ORDER BY timestamp
            """)
            
            for row in cur.fetchall():
                yield row['timestamp'], row['records']

    def all_records(self):
        """Iterate over all individual records"""
        with self._conn.cursor() as cur:
            cur.execute("""
                SELECT id, timestamp, base_id, status, taxi_id, created_at 
                FROM log_base_activity 
                ORDER BY timestamp, id
            """)
            
            for row in cur.fetchall():
                yield {
                    'id': row['id'],
                    'timestamp': row['timestamp'],
                    'base_id': row['base_id'],
                    'status': row['status'],
                    'taxi_id': row['taxi_id'],
                    'created_at': row['created_at']
                }

    def get_records_in_range(self, start_time: datetime, end_time: datetime) -> List[Dict[str, Any]]:
        """Get all records within a time range"""
        with self._conn.cursor() as cur:
            cur.execute("""
                SELECT id, timestamp, base_id, status, taxi_id, created_at 
                FROM log_base_activity 
                WHERE timestamp BETWEEN %s AND %s 
                ORDER BY timestamp, id
            """, (start_time, end_time))
            
            return [
                {
                    'id': row['id'],
                    'timestamp': row['timestamp'],
                    'base_id': row['base_id'],
                    'status': row['status'],
                    'taxi_id': row['taxi_id'],
                    'created_at': row['created_at']
                }
                for row in cur.fetchall()
            ]

    def count_records_by_timestamp(self, timestamp: datetime) -> int:
        """Count how many records exist for a specific timestamp"""
        with self._conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) as count FROM log_base_activity WHERE timestamp = %s", (timestamp,))
            return cur.fetchone()['count']

    def __repr__(self) -> str:
        all_logs = {ts: records for ts, records in self.items()}
        return repr(all_logs)

    def close(self):
        """Close the database connection"""
        if self._conn:
            self._conn.close()

dsn = "postgresql://appuser:secret123@db:5432/taxiAssignmentSystem"
log_base_activity = LogBaseActivityDB(dsn)
