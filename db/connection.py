import sqlite3
from app.config import DB_NAME

def get_connection():
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    return conn