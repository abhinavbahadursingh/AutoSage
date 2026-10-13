import psycopg2
import sys

# Try connecting with different methods
configs = [
    {"host": "localhost", "dbname": "postgres", "user": "postgres", "password": "postgres"},
    {"host": "localhost", "dbname": "postgres", "user": "postgres"},
    {"host": "127.0.0.1", "dbname": "postgres", "user": "postgres", "password": "postgres"},
    {"host": ".", "dbname": "postgres", "user": "postgres"},
]

for i, cfg in enumerate(configs):
    try:
        conn = psycopg2.connect(**cfg)
        cur = conn.cursor()
        cur.execute("SELECT 1")
        print(f"Config {i+1} SUCCESS: {cfg}")
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Config {i+1} FAILED: {cfg} -> {str(e)[:80]}")