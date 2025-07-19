import threading
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import uuid
import jwt
import datetime

class UserDataDB:
    def __init__(self, dsn: str):
        self._conn = psycopg2.connect(dsn, cursor_factory=RealDictCursor)
        self._lock = threading.Lock()
        self._ensure_table()

    def _ensure_table(self):
        with self._conn:
            with self._conn.cursor() as cur:
                cur.execute("""
                CREATE TABLE IF NOT EXISTS user_data (
                    user_id TEXT PRIMARY KEY,
                    username TEXT UNIQUE NOT NULL,
                    name TEXT NOT NULL,
                    password TEXT NOT NULL,
                    taxi_id TEXT REFERENCES taxi(taxi_id) ON DELETE SET NULL,
                    role TEXT NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                );
                """)

    def __getitem__(self, user_id: str) -> dict:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT username,name,password,taxi_id,role FROM user_data WHERE user_id=%s",
                (user_id,)
            )
            row = cur.fetchone()
            if not row:
                raise KeyError(f"User '{user_id}' tidak ditemukan")
            return dict(row)

    def get(self, user_id: str, default=None) -> dict:
        try:
            return self.__getitem__(user_id)
        except KeyError:
            return default

    def __setitem__(self, user_id: str, data: dict):
        with self._lock:
            with self._conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO user_data(user_id,username,name,password,taxi_id,role)
                    VALUES(%s,%s,%s,%s,%s,%s)
                    ON CONFLICT(user_id) DO UPDATE SET
                      username=EXCLUDED.username,
                      name=EXCLUDED.name,
                      password=EXCLUDED.password,
                      taxi_id=EXCLUDED.taxi_id,
                      role=EXCLUDED.role;
                    """,
                    (user_id, data['username'], data['name'], data['password'], data.get('taxi_id'), data['role'])
                )
            self._conn.commit()

    def pop(self, user_id: str, default=None) -> dict:
        old = self.get(user_id, default)
        with self._lock:
            with self._conn.cursor() as cur:
                cur.execute("DELETE FROM user_data WHERE user_id=%s", (user_id,))
            self._conn.commit()
        return old

    def items(self):
        with self._conn.cursor() as cur:
            cur.execute("SELECT user_id,username,name,password,taxi_id,role FROM user_data")
            for row in cur.fetchall():
                yield row.pop('user_id'), row

    def __repr__(self):
        return repr({uid: data for uid, data in self.items()})

dsn = "postgresql://appuser:secret123@db:5432/taxiAssignmentSystem"
user_data = UserDataDB(dsn)
