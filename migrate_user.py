from app import app, db, session_scope, User
import logging
import secrets
import string

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def generate_random_password(length=16):
    """Generate a random secure password"""
    # Define character sets
    lowercase = string.ascii_lowercase
    uppercase = string.ascii_uppercase
    digits = string.digits
    special = "!@#$%^&*"
    
    # Ensure password contains at least one character from each set
    password = [
        secrets.choice(lowercase),
        secrets.choice(uppercase),
        secrets.choice(digits),
        secrets.choice(special)
    ]
    
    # Fill the rest with random characters from all sets
    all_chars = lowercase + uppercase + digits + special
    for _ in range(length - 4):
        password.append(secrets.choice(all_chars))
    
    # Shuffle the password list to randomize positions
    secrets.SystemRandom().shuffle(password)
    
    return ''.join(password)

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
            
            # Create admin user or ask to overwrite if exists
            with session_scope() as db_session:
                admin = db_session.query(User).filter_by(username='admin').first()
                
                create_new_admin = False
                
                if not admin:
                    logger.info("Admin user not found, creating new admin user")
                    create_new_admin = True
                else:
                    logger.info("Admin user already exists")
                    print("\n" + "⚠️"*20)
                    print("🔐 ADMIN USER ALREADY EXISTS")
                    print("⚠️"*20)
                    print("An admin user already exists in the system.")
                    print("Do you want to overwrite it with a new password?")
                    print("⚠️"*20 + "\n")
                    
                    while True:
                        choice = input("Overwrite existing admin user? (y/N): ").strip().lower()
                        if choice in ['y', 'yes']:
                            create_new_admin = True
                            logger.info("User chose to overwrite existing admin")
                            break
                        elif choice in ['n', 'no', '']:
                            logger.info("User chose to keep existing admin")
                            print("Keeping existing admin user. No changes made.")
                            break
                        else:
                            print("Please enter 'y' for yes or 'n' for no.")
                
                if create_new_admin:
                    # Generate random password
                    random_password = generate_random_password()
                    
                    if admin:
                        # Update existing admin password
                        admin.set_password(random_password)
                        logger.info("Updated existing admin user password")
                        action = "UPDATED"
                    else:
                        # Create new admin
                        admin = User(username='admin')
                        admin.set_password(random_password)
                        db_session.add(admin)
                        logger.info("Created new admin user")
                        action = "CREATED"
                    
                    # Display password prominently
                    print("\n" + "="*60)
                    print(f"🔐 ADMIN PASSWORD {action}")
                    print("="*60)
                    print(f"Username: admin")
                    print(f"Password: {random_password}")
                    print("="*60)
                    print("⚠️  SAVE THIS PASSWORD NOW! It will not be shown again.")
                    print("="*60 + "\n")
                    
                    logger.info(f"Admin user {action.lower()} successfully")
                    logger.info(f"Admin password: {random_password}")
                    
            logger.info("User migration completed successfully")
    except Exception as e:
        logger.error(f"Error in user migration: {e}")
        raise

if __name__ == "__main__":
    add_user_table()
