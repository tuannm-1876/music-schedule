#!/usr/bin/env python3
"""
Migration script to add category column to Song table
and song_category column to Schedule table.
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance', 'music.db')

def migrate():
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}")
        return False
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Check if category column exists in song table
        cursor.execute("PRAGMA table_info(song)")
        song_columns = [col[1] for col in cursor.fetchall()]
        
        if 'category' not in song_columns:
            print("Adding 'category' column to song table...")
            cursor.execute("ALTER TABLE song ADD COLUMN category VARCHAR(20) DEFAULT 'music'")
            print("✓ Added 'category' column to song table")
        else:
            print("✓ 'category' column already exists in song table")
        
        # Check if song_category column exists in schedule table
        cursor.execute("PRAGMA table_info(schedule)")
        schedule_columns = [col[1] for col in cursor.fetchall()]
        
        if 'song_category' not in schedule_columns:
            print("Adding 'song_category' column to schedule table...")
            cursor.execute("ALTER TABLE schedule ADD COLUMN song_category VARCHAR(20) DEFAULT 'music'")
            print("✓ Added 'song_category' column to schedule table")
        else:
            print("✓ 'song_category' column already exists in schedule table")
        
        conn.commit()
        print("\n✓ Migration completed successfully!")
        return True
        
    except Exception as e:
        print(f"✗ Migration failed: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

if __name__ == '__main__':
    migrate()
