"""SQLite database module for Henjiu Relay"""

import aiosqlite
import secrets
import hashlib
from pathlib import Path
from typing import Optional

DB_PATH = Path(__file__).parent.parent / "data" / "henjiu.db"


async def init_db():
    """Initialize database tables"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    async with aiosqlite.connect(DB_PATH) as db:
        # Users table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                api_key TEXT UNIQUE,
                role TEXT DEFAULT 'user',
                enabled INTEGER DEFAULT 1,
                is_root INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Instances table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS instances (
                id TEXT PRIMARY KEY,
                name TEXT,
                url TEXT NOT NULL,
                auth_type TEXT DEFAULT 'bearer',
                auth_token TEXT,
                auth_username TEXT,
                auth_password TEXT,
                api_token TEXT,
                auth_token_ws TEXT,
                enabled INTEGER DEFAULT 1,
                timeout REAL DEFAULT 30,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Sessions table (for logging/audit)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                instance_id TEXT,
                session_key TEXT,
                channel TEXT,
                sender_id TEXT,
                connected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                disconnected_at TIMESTAMP,
                messages_count INTEGER DEFAULT 0
            )
        """)
        
        await db.commit()
    
    return DB_PATH


async def get_user_by_api_key(api_key: str) -> Optional[dict]:
    """Get user by API key"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM users WHERE api_key = ? AND enabled = 1", (api_key,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def get_user_by_credentials(username: str, password: str) -> Optional[dict]:
    """Get user by username and password"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM users WHERE username = ? AND password = ? AND enabled = 1",
            (username, password)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def list_users() -> list[dict]:
    """List all users"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT id, username, api_key, role, enabled, created_at FROM users") as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def add_user(username: str, password: str, role: str = "user", api_key: Optional[str] = None, is_root: bool = False) -> dict:
    """Add a new user"""
    if not api_key:
        api_key = secrets.token_urlsafe(32)
    
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO users (username, password, api_key, role, is_root) VALUES (?, ?, ?, ?, ?)",
            (username, password, api_key, role, 1 if is_root else 0)
        )
        await db.commit()
    
    return {"username": username, "api_key": api_key, "role": role}


async def delete_user(username: str) -> bool:
    """Delete a user (cannot delete root users)"""
    # Check if user is root
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT is_root FROM users WHERE username = ?", (username,))
        row = await cursor.fetchone()
        if row and row[0] == 1:
            return False  # Cannot delete root user
    
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("DELETE FROM users WHERE username = ?", (username,))
        await db.commit()
        return cursor.rowcount > 0


async def regenerate_user_api_key(username: str) -> Optional[str]:
    """Regenerate user's API key"""
    new_key = secrets.token_urlsafe(32)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET api_key = ? WHERE username = ?", (new_key, username)
        )
        await db.commit()
    return new_key


async def update_user_password(username: str, new_password: str) -> bool:
    """Update user password"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET password = ? WHERE username = ?", (new_password, username)
        )
        await db.commit()
    return True


async def get_instance(instance_id: str) -> Optional[dict]:
    """Get instance by ID"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM instances WHERE id = ?", (instance_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def list_instances() -> list[dict]:
    """List all instances"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM instances") as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def add_instance(
    instance_id: str,
    name: str,
    url: str,
    auth_type: str = "bearer",
    auth_token: str = "",
    enabled: bool = True,
    timeout: float = 30.0,
) -> dict:
    """Add a new instance"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT OR REPLACE INTO instances 
               (id, name, url, auth_type, auth_token, enabled, timeout) 
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (instance_id, name, url, auth_type, auth_token, 1 if enabled else 0, timeout)
        )
        await db.commit()
    return {"id": instance_id, "name": name, "url": url}


async def delete_instance(instance_id: str) -> bool:
    """Delete an instance"""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("DELETE FROM instances WHERE id = ?", (instance_id,))
        await db.commit()
        return cursor.rowcount > 0


async def update_instance(instance_id: str, **kwargs) -> bool:
    """Update instance settings"""
    fields = ", ".join(f"{k} = ?" for k in kwargs.keys())
    values = list(kwargs.values()) + [instance_id]
    
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(f"UPDATE instances SET {fields} WHERE id = ?", values)
        await db.commit()
    return True


async def log_session(instance_id: str, session_key: str, channel: str = "", sender_id: str = ""):
    """Log a new session"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO sessions (instance_id, session_key, channel, sender_id) VALUES (?, ?, ?, ?)",
            (instance_id, session_key, channel, sender_id)
        )
        await db.commit()


async def close_session(instance_id: str):
    """Mark session as closed"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE sessions SET disconnected_at = CURRENT_TIMESTAMP WHERE instance_id = ? AND disconnected_at IS NULL",
            (instance_id,)
        )
        await db.commit()


async def get_db_path() -> Path:
    """Get database file path"""
    return DB_PATH
