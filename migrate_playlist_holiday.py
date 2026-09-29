#!/usr/bin/env python3
"""Migration script to add Playlist and Holiday tables, and playlist_id columns to Song and Schedule.
Also migrates existing song categories and schedule song_categories to playlists."""

import sqlite3
import os
import sys

def migrate():
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance', 'music.db')
    
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        print("The tables will be created automatically when the app starts.")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Create Playlist table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS playlist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name VARCHAR(100) NOT NULL UNIQUE,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("✓ Created playlist table")
        
        # Create Holiday table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS holiday (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date VARCHAR(10) NOT NULL UNIQUE,
                name VARCHAR(200) NOT NULL
            )
        """)
        print("✓ Created holiday table")
        
        # Add playlist_id to Song table
        cursor.execute("PRAGMA table_info(song)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'playlist_id' not in columns:
            cursor.execute("ALTER TABLE song ADD COLUMN playlist_id INTEGER REFERENCES playlist(id)")
            print("✓ Added playlist_id column to song table")
        else:
            print("- playlist_id column already exists in song table")
        
        # Add playlist_id to Schedule table
        cursor.execute("PRAGMA table_info(schedule)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'playlist_id' not in columns:
            cursor.execute("ALTER TABLE schedule ADD COLUMN playlist_id INTEGER REFERENCES playlist(id)")
            print("✓ Added playlist_id column to schedule table")
        else:
            print("- playlist_id column already exists in schedule table")
        
        # Auto-migrate existing categories to playlists
        # Check if there are songs with category='announcement' that need migration
        cursor.execute("PRAGMA table_info(song)")
        song_columns = [col[1] for col in cursor.fetchall()]
        
        if 'category' in song_columns:
            # Check for announcement songs not yet assigned to a playlist
            cursor.execute("SELECT COUNT(*) FROM song WHERE category = 'announcement' AND (playlist_id IS NULL OR playlist_id = 0)")
            announcement_count = cursor.fetchone()[0]
            
            if announcement_count > 0:
                # Create 'Truyền thông' playlist if it doesn't exist
                cursor.execute("SELECT id FROM playlist WHERE name = 'Truyền thông'")
                row = cursor.fetchone()
                if row:
                    announcement_playlist_id = row[0]
                else:
                    cursor.execute("INSERT INTO playlist (name) VALUES ('Truyền thông')")
                    announcement_playlist_id = cursor.lastrowid
                    print(f"✓ Created 'Truyền thông' playlist (id={announcement_playlist_id})")
                
                # Assign announcement songs to the playlist
                cursor.execute(
                    "UPDATE song SET playlist_id = ? WHERE category = 'announcement' AND (playlist_id IS NULL OR playlist_id = 0)",
                    (announcement_playlist_id,)
                )
                print(f"✓ Migrated {announcement_count} announcement songs to 'Truyền thông' playlist")
            
            # Migrate schedule song_categories to playlists
            cursor.execute("PRAGMA table_info(schedule)")
            schedule_columns = [col[1] for col in cursor.fetchall()]
            
            if 'song_category' in schedule_columns:
                cursor.execute("SELECT COUNT(*) FROM schedule WHERE song_category = 'announcement' AND (playlist_id IS NULL OR playlist_id = 0)")
                schedule_count = cursor.fetchone()[0]
                
                if schedule_count > 0:
                    # Ensure announcement playlist exists
                    cursor.execute("SELECT id FROM playlist WHERE name = 'Truyền thông'")
                    row = cursor.fetchone()
                    if row:
                        announcement_playlist_id = row[0]
                    else:
                        cursor.execute("INSERT INTO playlist (name) VALUES ('Truyền thông')")
                        announcement_playlist_id = cursor.lastrowid
                    
                    cursor.execute(
                        "UPDATE schedule SET playlist_id = ? WHERE song_category = 'announcement' AND (playlist_id IS NULL OR playlist_id = 0)",
                        (announcement_playlist_id,)
                    )
                    print(f"✓ Migrated {schedule_count} announcement schedules to 'Truyền thông' playlist")
        
        conn.commit()
        print("\nMigration completed successfully!")
        
    except Exception as e:
        conn.rollback()
        print(f"Migration failed: {e}")
        sys.exit(1)
    finally:
        conn.close()

if __name__ == '__main__':
    migrate()
