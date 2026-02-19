"""One-time DB fix: create any missing tables."""
import sqlite3, os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'humetix.db')

# 1. Check existing tables
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
existing = [row[0] for row in cursor.fetchall()]
print(f"DB path: {DB_PATH}")
print(f"Existing tables: {existing}")
conn.close()

# 2. Use Flask-SQLAlchemy to create any missing tables
os.environ.setdefault('SECRET_KEY', 'your_secret_key')
os.environ.setdefault('ADMIN_PASSWORD', '3326')

from app import app
from models import db

with app.app_context():
    db.create_all()
    print("db.create_all() completed!")

# 3. Re-check tables
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
after = [row[0] for row in cursor.fetchall()]
print(f"Tables after fix: {after}")
conn.close()

print("\nDone! You can delete this file now and restart the server.")
