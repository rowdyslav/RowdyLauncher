import sqlite3

DB_CONN = sqlite3.connect("database.db", check_same_thread=False)
DB_CURSOR = DB_CONN.cursor()

DB_CURSOR.execute("""CREATE TABLE IF NOT EXISTS users (login TEXT, password TEXT);""")
DB_CURSOR.execute(
    """CREATE TABLE IF NOT EXISTS stats (version TEXT, launches INTEGER, release DATE);"""
)
