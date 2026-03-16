import database, models, auth
from sqlalchemy.orm import Session
import os

def reset_password():
    db = database.SessionLocal()
    try:
        user = db.query(models.User).filter(models.User.username == "admin").first()
        if user:
            user.hashed_password = auth.get_password_hash("admin123")
            db.commit()
            print("Successfully reset password for user: admin")
        else:
            print("User admin not found")
    finally:
        db.close()

if __name__ == "__main__":
    reset_password()
