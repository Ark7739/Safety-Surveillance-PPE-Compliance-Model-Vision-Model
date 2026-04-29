"""
SQLite Database Manager for PPE Compliance
============================================
Manages violation logs, session records, and compliance reports.
"""

import sqlite3
import json
import os
from datetime import datetime
from pathlib import Path
from contextlib import contextmanager

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "ppe_compliance.db"


class ComplianceDB:
    """SQLite database manager for PPE compliance data."""

    def __init__(self, db_path=None):
        self.db_path = str(db_path or DB_PATH)
        self._init_db()

    def _init_db(self):
        """Initialize database tables."""
        with self._get_conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    start_time TEXT NOT NULL,
                    end_time TEXT,
                    source TEXT,
                    total_frames INTEGER DEFAULT 0,
                    total_persons_detected INTEGER DEFAULT 0,
                    total_violations INTEGER DEFAULT 0,
                    avg_compliance_rate REAL DEFAULT 0.0,
                    status TEXT DEFAULT 'active'
                );

                CREATE TABLE IF NOT EXISTS violations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER,
                    timestamp TEXT NOT NULL,
                    person_id INTEGER,
                    missing_ppe TEXT,
                    confidence REAL,
                    bbox TEXT,
                    frame_number INTEGER,
                    FOREIGN KEY (session_id) REFERENCES sessions(id)
                );

                CREATE TABLE IF NOT EXISTS compliance_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER,
                    timestamp TEXT NOT NULL,
                    compliance_rate REAL,
                    total_persons INTEGER,
                    compliant_persons INTEGER,
                    frame_number INTEGER,
                    detection_counts TEXT,
                    FOREIGN KEY (session_id) REFERENCES sessions(id)
                );

                CREATE INDEX IF NOT EXISTS idx_violations_session ON violations(session_id);
                CREATE INDEX IF NOT EXISTS idx_violations_timestamp ON violations(timestamp);
                CREATE INDEX IF NOT EXISTS idx_snapshots_session ON compliance_snapshots(session_id);
            """)

    @contextmanager
    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    # --- Session Management ---

    def create_session(self, source="webcam"):
        with self._get_conn() as conn:
            cursor = conn.execute(
                "INSERT INTO sessions (start_time, source) VALUES (?, ?)",
                (datetime.now().isoformat(), source)
            )
            return cursor.lastrowid

    def end_session(self, session_id, total_frames=0):
        with self._get_conn() as conn:
            # Calculate average compliance
            row = conn.execute(
                "SELECT AVG(compliance_rate) as avg_rate, SUM(total_persons) as total_p "
                "FROM compliance_snapshots WHERE session_id = ?",
                (session_id,)
            ).fetchone()
            
            avg_rate = row['avg_rate'] or 0.0
            total_persons = row['total_p'] or 0

            violation_count = conn.execute(
                "SELECT COUNT(*) as cnt FROM violations WHERE session_id = ?",
                (session_id,)
            ).fetchone()['cnt']

            conn.execute(
                "UPDATE sessions SET end_time=?, total_frames=?, total_persons_detected=?, "
                "total_violations=?, avg_compliance_rate=?, status='completed' WHERE id=?",
                (datetime.now().isoformat(), total_frames, total_persons,
                 violation_count, avg_rate, session_id)
            )

    def get_session(self, session_id):
        with self._get_conn() as conn:
            row = conn.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()
            return dict(row) if row else None

    def get_recent_sessions(self, limit=10):
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM sessions ORDER BY start_time DESC LIMIT ?", (limit,)
            ).fetchall()
            return [dict(r) for r in rows]

    # --- Violation Logging ---

    def log_violation(self, session_id, person_id, missing_ppe, confidence,
                      bbox=None, frame_number=0):
        with self._get_conn() as conn:
            conn.execute(
                "INSERT INTO violations (session_id, timestamp, person_id, missing_ppe, "
                "confidence, bbox, frame_number) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (session_id, datetime.now().isoformat(), person_id,
                 json.dumps(missing_ppe), confidence,
                 json.dumps(bbox) if bbox else None, frame_number)
            )

    def get_violations(self, session_id=None, limit=100):
        with self._get_conn() as conn:
            if session_id:
                rows = conn.execute(
                    "SELECT * FROM violations WHERE session_id=? ORDER BY timestamp DESC LIMIT ?",
                    (session_id, limit)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM violations ORDER BY timestamp DESC LIMIT ?", (limit,)
                ).fetchall()
            results = []
            for r in rows:
                d = dict(r)
                d['missing_ppe'] = json.loads(d['missing_ppe']) if d['missing_ppe'] else []
                d['bbox'] = json.loads(d['bbox']) if d['bbox'] else None
                results.append(d)
            return results

    # --- Compliance Snapshots ---

    def log_snapshot(self, session_id, compliance_rate, total_persons,
                     compliant_persons, frame_number, detection_counts=None):
        with self._get_conn() as conn:
            conn.execute(
                "INSERT INTO compliance_snapshots (session_id, timestamp, compliance_rate, "
                "total_persons, compliant_persons, frame_number, detection_counts) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (session_id, datetime.now().isoformat(), compliance_rate,
                 total_persons, compliant_persons, frame_number,
                 json.dumps(detection_counts) if detection_counts else None)
            )

    def get_compliance_history(self, session_id, limit=500):
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM compliance_snapshots WHERE session_id=? "
                "ORDER BY timestamp ASC LIMIT ?",
                (session_id, limit)
            ).fetchall()
            results = []
            for r in rows:
                d = dict(r)
                d['detection_counts'] = json.loads(d['detection_counts']) \
                    if d['detection_counts'] else {}
                results.append(d)
            return results

    # --- Reports ---

    def generate_report(self, session_id):
        session = self.get_session(session_id)
        if not session:
            return None

        violations = self.get_violations(session_id, limit=1000)
        history = self.get_compliance_history(session_id, limit=1000)

        # Aggregate violation types
        violation_summary = {}
        for v in violations:
            for ppe in v['missing_ppe']:
                violation_summary[ppe] = violation_summary.get(ppe, 0) + 1

        return {
            "session": session,
            "total_violations": len(violations),
            "violation_summary": violation_summary,
            "violations": violations[:50],  # Latest 50
            "compliance_history": history,
            "generated_at": datetime.now().isoformat()
        }

    def get_dashboard_stats(self, session_id=None):
        with self._get_conn() as conn:
            if session_id:
                violations = conn.execute(
                    "SELECT COUNT(*) as cnt FROM violations WHERE session_id=?",
                    (session_id,)
                ).fetchone()['cnt']
                
                latest = conn.execute(
                    "SELECT * FROM compliance_snapshots WHERE session_id=? "
                    "ORDER BY timestamp DESC LIMIT 1",
                    (session_id,)
                ).fetchone()
            else:
                violations = conn.execute(
                    "SELECT COUNT(*) as cnt FROM violations"
                ).fetchone()['cnt']
                latest = None

            sessions_count = conn.execute(
                "SELECT COUNT(*) as cnt FROM sessions"
            ).fetchone()['cnt']

            return {
                "total_violations": violations,
                "total_sessions": sessions_count,
                "latest_snapshot": dict(latest) if latest else None
            }
