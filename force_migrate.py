import sys
import os
sys.path.append(os.path.join(os.getcwd(), 'backend'))
from database import SessionLocal
from sqlalchemy import text
from models import LearningPath, Course

db = SessionLocal()
try:
    paths = db.query(LearningPath).all()
    for path in paths:
        result = db.execute(text(f"SELECT id FROM modules WHERE path_id = {path.id}"))
        module_ids = [row[0] for row in result]
        
        if module_ids:
            print(f"Path {path.title} has orphaned modules: {module_ids}")
            # Create a default course for this path
            default_course = Course(path_id=path.id, title="Módulos Gerais (Migrados)", description="Módulos gerados a partir da transição da versão anterior.", order=1)
            db.add(default_course)
            db.flush()
            
            # Update modules
            id_list = ','.join(map(str, module_ids))
            db.execute(text(f"UPDATE modules SET course_id = {default_course.id} WHERE id IN ({id_list})"))
            db.commit()
            print("Successfully migrated.")
except Exception as e:
    print(f"Failed: {e}")
finally:
    db.close()
