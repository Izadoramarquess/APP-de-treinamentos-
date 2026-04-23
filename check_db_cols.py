import sys
import os
sys.path.append(os.path.join(os.getcwd(), 'backend'))
from database import engine

with engine.connect() as conn:
    res = conn.execute("PRAGMA table_info(modules);")
    cols = [(r[1], r[2]) for r in res]
    print(f"Columns in modules: {cols}")
