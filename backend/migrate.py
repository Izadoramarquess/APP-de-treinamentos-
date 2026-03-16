import sqlite3
import os

db_path = r"c:\Users\8000295\.gemini\antigravity\scratch\training-platform\backend\training_platform.db"

if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    try:
        cursor.execute("ALTER TABLE trainings ADD COLUMN thumbnail_url TEXT")
        print("Column thumbnail_url added successfully.")
    except sqlite3.OperationalError:
        print("Column thumbnail_url already exists or table doesn't exist.")
    conn.commit()
    conn.close()
else:
    print("Database file not found at " + db_path)
