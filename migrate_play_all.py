"""Migration: Add play_all column to Schedule table"""
import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Try both possible database filenames
_db_candidates = [
    os.path.join(BASE_DIR, 'instance', 'music.db'),
    os.path.join(BASE_DIR, 'instance', 'music_scheduler.db'),
]
DB_PATH = next((p for p in _db_candidates if os.path.exists(p)), _db_candidates[0])

def migrate():
    print(f"Connecting to database: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Check if the column already exists
    cursor.execute("PRAGMA table_info(schedule)")
    columns = [row[1] for row in cursor.fetchall()]

    if 'play_all' not in columns:
        print("Adding 'play_all' column to 'schedule' table...")
        cursor.execute("ALTER TABLE schedule ADD COLUMN play_all BOOLEAN DEFAULT 0 NOT NULL")
        conn.commit()
        print("Migration complete: 'play_all' column added successfully.")
    else:
        print("Column 'play_all' already exists. No migration needed.")

    conn.close()

if __name__ == '__main__':
    migrate()
