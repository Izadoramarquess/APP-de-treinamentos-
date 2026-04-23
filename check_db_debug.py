import sys
import os
sys.path.append(os.path.join(os.getcwd(), 'backend'))
from database import SessionLocal, engine
from sqlalchemy import text
import models

db = SessionLocal()
try:
    print("Checking tables...")
    with engine.connect() as conn:
        res = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
        tables = [r[0] for r in res]
        print(f"Tables: {tables}")
        
    if 'modules' in tables:
        count = db.query(models.Module).count()
        orphans = db.query(models.Module).filter(models.Module.course_id == None).all()
        print(f"Total modules: {count}")
        print(f"Orphaned modules count: {len(orphans)}")
        for m in orphans:
            print(f"Orphan: ID={m.id}, Title='{m.title}'")
        
    if 'courses' in tables:
        count = db.query(models.Course).count()
        print(f"Total courses: {count}")
        courses = db.query(models.Course).all()
        for c in courses:
            print(f"Course: ID={c.id}, Title='{c.title}', PathID={c.path_id}")

except Exception as e:
    print(f"Error: {e}")
finally:
    db.close()
