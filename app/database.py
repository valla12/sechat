import asyncio
import aiosqlite
import bcrypt

DB_NAME = "chat.db"

def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
    except ValueError:
        return False

async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id TEXT NOT NULL,
                username TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS groups (
                group_id TEXT PRIMARY KEY,
                group_name TEXT NOT NULL,
                password TEXT NOT NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                password TEXT NOT NULL
            )
        """)
        await db.commit()

async def create_user(username: str, password: str):
    hashed = await asyncio.to_thread(hash_password, password)
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, hashed))
        await db.commit()

async def verify_user(username: str, password: str):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT password FROM users WHERE username = ?", (username,))
        row = await cursor.fetchone()
        if row is None:
            return False
        return await asyncio.to_thread(verify_password, password, row[0])

async def create_group(group_id: str, group_name: str, password: str):
    hashed_password = await asyncio.to_thread(hash_password, password)
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT INTO groups (group_id, group_name, password) VALUES (?, ?, ?)",
            (group_id, group_name, hashed_password)
        )
        await db.commit()

async def verify_group(group_id: str, password: str):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT password FROM groups WHERE group_id = ?", (group_id,))
        row = await cursor.fetchone()
        if row is None:
            return False
        return await asyncio.to_thread(verify_password, password, row[0])

async def save_message(group_id: str, username: str, content: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT INTO messages (group_id, username, content) VALUES (?, ?, ?)",
            (group_id, username, content)
        )
        await db.commit()

async def get_group_history(group_id: str, limit: int = 50):
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT username, content FROM messages WHERE group_id = ? ORDER BY id DESC LIMIT ?",
            (group_id, limit)
        )
        rows = await cursor.fetchall()
        return [{"username": row["username"], "content": row["content"]} for row in reversed(rows)]

async def clear_group_messages(group_id: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("DELETE FROM messages WHERE group_id = ?", (group_id,))
        await db.commit()

async def clear_all_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("DELETE FROM messages")
        await db.execute("DELETE FROM groups")
        await db.execute("DELETE FROM users")
        await db.commit()
