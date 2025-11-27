#!/usr/bin/env python3
"""
Migration script to add delete_after_play column to Song table.
Run this script to add the new column to existing databases.
"""

import sqlite3
import os

def migrate():
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance', 'music.db')
    
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        print("The column will be created automatically when the app starts.")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check if column already exists
        cursor.execute("PRAGMA table_info(song)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'delete_after_play' in columns:
            print("Column 'delete_after_play' already exists in 'song' table.")
            return
        
        # Add the new column
        cursor.execute("ALTER TABLE song ADD COLUMN delete_after_play BOOLEAN DEFAULT 0")
        conn.commit()
        print("Successfully added 'delete_after_play' column to 'song' table.")
        
    except Exception as e:
        print(f"Error during migration: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == '__main__':
    migrate()
