import sys
import os
sys.path.append(os.path.join(os.getcwd(), 'backend'))
from database import SessionLocal
import models

db = SessionLocal()
try:
    user = db.query(models.User).filter(models.User.email == "izadora.silva@geobiogas.tech").first()
    if user:
        print(f"User found: ID={user.id}")
        print(f"Username: {user.username}")
        print(f"Email: {user.email}")
        print(f"Role: {user.role}")
        print(f"Status: {user.status}")
        print(f"Team ID: {user.team_id}")
        print(f"Invite Token: {user.invite_token}")
        print(f"Invite Expires At: {user.invite_expires_at}")
        
        # Check team
        if user.team_id:
            team = db.query(models.Team).filter(models.Team.id == user.team_id).first()
            if team:
                print(f"Team Name: {team.name}")
            else:
                print("Team ID exists but Team not found!")
    else:
        print("User NOT FOUND in database.")
except Exception as e:
    print(f"Error querying user: {e}")
finally:
    db.close()
