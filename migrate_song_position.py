from app import app, db, session_scope, Song
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def add_position_field():
    """Add position field to the Song model"""
    try:
        with app.app_context():
            # Check if the position field already exists
            inspector = db.inspect(db.engine)
            columns = [column['name'] for column in inspector.get_columns('song')]
            
            if 'position' not in columns:
                logger.info("Adding position column to Song table")
                # SQLAlchemy 2.0 syntax
                with db.engine.connect() as connection:
                    from sqlalchemy import text
                    connection.execute(text("ALTER TABLE song ADD COLUMN position INTEGER DEFAULT 0"))
                    connection.commit()
                    logger.info("Position column added successfully")
            else:
                logger.info("Position column already exists")
            
            # Update all songs with position based on current order
            with session_scope() as session:
                logger.info("Updating song positions...")
                songs = session.query(Song).order_by(
                    Song.last_played_at.is_(None).desc(),
                    Song.priority.desc(),
                    Song.last_played_at.asc()
                ).all()
                
                for i, song in enumerate(songs):
                    song.position = i
                    logger.info(f"Setting position {i} for song {song.id}: {song.title}")
                    
                logger.info(f"Updated positions for {len(songs)} songs")
                
            logger.info("Migration completed successfully")
    except Exception as e:
        logger.error(f"Error in migration: {e}")
        raise

if __name__ == "__main__":
    add_position_field()
