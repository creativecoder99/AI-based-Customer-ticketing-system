import sqlite3
import json
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from contextlib import contextmanager
from src.config import DATABASE_PATH


def get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Establish a connection to the SQLite database with row factory and foreign keys enabled."""
    target_path = db_path or DATABASE_PATH
    conn = sqlite3.connect(target_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


@contextmanager
def get_db_context(db_path: Optional[str] = None):
    """Context manager for SQLite database transactions."""
    conn = get_connection(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(db_path: Optional[str] = None) -> None:
    """Initialize SQLite database tables according to the required schema."""
    with get_db_context(db_path) as conn:
        cursor = conn.cursor()
        
        # 1. Users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL
            );
        """)

        # 2. Tickets table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                message TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );
        """)

        # 3. Decisions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                reason TEXT NOT NULL,
                confidence REAL NOT NULL,
                sources TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL,
                FOREIGN KEY (ticket_id) REFERENCES tickets(id) ON DELETE CASCADE
            );
        """)
        
        # Create useful indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tickets_user_id ON tickets(user_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_decisions_ticket_id ON decisions(ticket_id);")


def create_user(email: str, password_hash: str, db_path: Optional[str] = None) -> Dict[str, Any]:
    """Insert a new user record."""
    created_at = datetime.now(timezone.utc).isoformat()
    with get_db_context(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO users (email, password_hash, created_at) VALUES (?, ?, ?)",
            (email.strip().lower(), password_hash, created_at)
        )
        user_id = cursor.lastrowid
        return {
            "id": user_id,
            "email": email.strip().lower(),
            "created_at": created_at
        }


def get_user_by_email(email: str, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Retrieve user record by email."""
    with get_db_context(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email = ?", (email.strip().lower(),))
        row = cursor.fetchone()
        return dict(row) if row else None


def get_user_by_id(user_id: int, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Retrieve user record by ID."""
    with get_db_context(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, email, created_at FROM users WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def create_ticket(user_id: int, message: str, db_path: Optional[str] = None) -> Dict[str, Any]:
    """Insert a new ticket submitted by a user."""
    created_at = datetime.now(timezone.utc).isoformat()
    with get_db_context(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO tickets (user_id, message, created_at) VALUES (?, ?, ?)",
            (user_id, message.strip(), created_at)
        )
        ticket_id = cursor.lastrowid
        return {
            "id": ticket_id,
            "user_id": user_id,
            "message": message.strip(),
            "created_at": created_at
        }


def create_decision(
    ticket_id: int,
    action: str,
    reason: str,
    confidence: float,
    sources: List[str],
    db_path: Optional[str] = None
) -> Dict[str, Any]:
    """Persist an AI decision associated with a ticket."""
    created_at = datetime.now(timezone.utc).isoformat()
    sources_json = json.dumps(sources)
    with get_db_context(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO decisions (ticket_id, action, reason, confidence, sources, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (ticket_id, action, reason, confidence, sources_json, created_at)
        )
        decision_id = cursor.lastrowid
        return {
            "id": decision_id,
            "ticket_id": ticket_id,
            "action": action,
            "reason": reason,
            "confidence": confidence,
            "sources": sources,
            "created_at": created_at
        }


def get_tickets_by_user(user_id: int, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Return all tickets belonging to a user with their associated decisions."""
    with get_db_context(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT 
                t.id, t.user_id, t.message, t.created_at,
                d.id AS decision_id, d.action, d.reason, d.confidence, d.sources, d.created_at AS decision_created_at
            FROM tickets t
            LEFT JOIN decisions d ON d.ticket_id = t.id
            WHERE t.user_id = ?
            ORDER BY t.id DESC
            """,
            (user_id,)
        )
        rows = cursor.fetchall()
        results = []
        for r in rows:
            sources_val = []
            if r["sources"]:
                try:
                    sources_val = json.loads(r["sources"])
                except Exception:
                    sources_val = [r["sources"]]
            
            decision = None
            if r["decision_id"]:
                decision = {
                    "id": r["decision_id"],
                    "ticket_id": r["id"],
                    "action": r["action"],
                    "reason": r["reason"],
                    "confidence": r["confidence"],
                    "sources": sources_val,
                    "created_at": r["decision_created_at"]
                }
            results.append({
                "id": r["id"],
                "user_id": r["user_id"],
                "message": r["message"],
                "created_at": r["created_at"],
                "decision": decision
            })
        return results


def get_ticket_by_id(ticket_id: int, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Return a single ticket and its decision."""
    with get_db_context(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT 
                t.id, t.user_id, t.message, t.created_at,
                d.id AS decision_id, d.action, d.reason, d.confidence, d.sources, d.created_at AS decision_created_at
            FROM tickets t
            LEFT JOIN decisions d ON d.ticket_id = t.id
            WHERE t.id = ?
            """,
            (ticket_id,)
        )
        r = cursor.fetchone()
        if not r:
            return None
        
        sources_val = []
        if r["sources"]:
            try:
                sources_val = json.loads(r["sources"])
            except Exception:
                sources_val = [r["sources"]]
                
        decision = None
        if r["decision_id"]:
            decision = {
                "id": r["decision_id"],
                "ticket_id": r["id"],
                "action": r["action"],
                "reason": r["reason"],
                "confidence": r["confidence"],
                "sources": sources_val,
                "created_at": r["decision_created_at"]
            }
            
        return {
            "id": r["id"],
            "user_id": r["user_id"],
            "message": r["message"],
            "created_at": r["created_at"],
            "decision": decision
        }
