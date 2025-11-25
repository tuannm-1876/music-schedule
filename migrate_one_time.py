#!/usr/bin/env python3
"""
Migration script to add one_time column to Schedule table.
Run this once to update existing database.
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
        # Check if column already exists
        cursor.execute("PRAGMA table_info(schedule)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'one_time' in columns:
            print("Column 'one_time' already exists in schedule table")
            return True
        
        # Add the column
        cursor.execute("ALTER TABLE schedule ADD COLUMN one_time BOOLEAN DEFAULT 0")
        conn.commit()
        print("Successfully added 'one_time' column to schedule table")
        return True
        
    except Exception as e:
        print(f"Error during migration: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

if __name__ == '__main__':
    migrate()
