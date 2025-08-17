import sqlite3
from .env import get_paths

def init_db():
    p = get_paths()
    conn = sqlite3.connect(p["BACKEND_DB"])
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS activaciones (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        token TEXT NOT NULL UNIQUE,
        device_id TEXT,
        fecha_creacion TEXT NOT NULL,
        usado INTEGER DEFAULT 0,
        fecha_uso TEXT
    )""")
    conn.commit()
    conn.close()

def insert_token(token):
    p = get_paths()
    conn = sqlite3.connect(p["BACKEND_DB"])
    c = conn.cursor()
    c.execute("INSERT INTO activaciones (token, fecha_creacion) VALUES (?, datetime('now'))", (token,))
    conn.commit()
    conn.close()
