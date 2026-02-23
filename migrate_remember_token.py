"""Migration script to add remember_token column to User table."""
import sqlite3
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate():
    db_path = os.path.join(os.path.dirname(__file__), 'instance', 'music.db')
    
    if not os.path.exists(db_path):
        logger.error(f"Database not found at {db_path}")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check if column already exists
    cursor.execute("PRAGMA table_info(user)")
    columns = [col[1] for col in cursor.fetchall()]
    
    if 'remember_token' in columns:
        logger.info("Column 'remember_token' already exists in User table. Skipping.")
    else:
        cursor.execute("ALTER TABLE user ADD COLUMN remember_token VARCHAR(100)")
        cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_user_remember_token ON user(remember_token)")
        conn.commit()
        logger.info("Added 'remember_token' column with unique index to User table.")
    
    conn.close()
    logger.info("Migration complete.")

if __name__ == '__main__':
    migrate()
