from app import app, db, session_scope, User
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def add_user_table():
    """Add User table and create admin user"""
    try:
        with app.app_context():
            # Check if the User table exists
            inspector = db.inspect(db.engine)
            tables = inspector.get_table_names()
            
            if 'user' not in tables:
                logger.info("Creating User table")
                db.create_all()
                logger.info("User table created successfully")
            else:
                logger.info("User table already exists")
            
            # Create admin user if it doesn't exist
            with session_scope() as db_session:
                admin = db_session.query(User).filter_by(username='admin').first()
                if not admin:
                    logger.info("Creating admin user")
                    admin = User(username='admin')
                    admin.set_password('Sun123@')
                    db_session.add(admin)
                    logger.info("Admin user created successfully")
                else:
                    logger.info("Admin user already exists")
                    
            logger.info("User migration completed successfully")
    except Exception as e:
        logger.error(f"Error in user migration: {e}")
        raise

if __name__ == "__main__":
    add_user_table()
