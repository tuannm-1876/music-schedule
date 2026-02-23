#!/usr/bin/env python3
"""
Migration script to add volume column to Schedule table.
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
        # Check if volume column exists in schedule table
        cursor.execute("PRAGMA table_info(schedule)")
        schedule_columns = [col[1] for col in cursor.fetchall()]
        
        if 'volume' not in schedule_columns:
            print("Adding 'volume' column to schedule table...")
            cursor.execute("ALTER TABLE schedule ADD COLUMN volume INTEGER DEFAULT 100")
            print("✓ Added 'volume' column to schedule table")
            
            # Update existing schedules to have default volume of 100
            cursor.execute("UPDATE schedule SET volume = 100 WHERE volume IS NULL")
            print("✓ Set default volume (100) for existing schedules")
        else:
            print("✓ 'volume' column already exists in schedule table")
        
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
    print("=" * 60)
    print("Schedule Volume Migration")
    print("=" * 60)
    print()
    
    success = migrate()
    
    if success:
        print("\nMigration completed! You can now restart the application.")
    else:
        print("\nMigration failed. Please check the error messages above.")
    
    print()
