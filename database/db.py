import sqlite3
import os
from datetime import datetime

class ForestFireDB:
    def __init__(self, db_path="/home/pi/lesnoj_strazh/database/lesnoj_strazh.db"):
        """
        Initializes the database connection and creates the table if it doesn't exist.
        """
        self.db_path = db_path
        # Ensure the directory exists
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.init_db()

    def init_db(self):
        """
        Creates the fires table.
        Columns: id, timestamp, latitude, longitude, confidence, status
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS fires (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    latitude REAL,
                    longitude REAL,
                    confidence REAL,
                    status TEXT
                )
            ''')
            conn.commit()

    def log_fire(self, lat, lon, confidence, status="DETECTED"):
        """
        Inserts a new fire record into the database.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cursor.execute('''
                    INSERT INTO fires (timestamp, latitude, longitude, confidence, status)
                    VALUES (?, ?, ?, ?, ?)
                ''', (timestamp, lat, lon, confidence, status))
                conn.commit()
                print(f"Fire logged at {timestamp}")
        except Exception as e:
            print(f"Database error: {e}")

# Self-test block: creates the DB when the script is run directly
if __name__ == "__main__":
    db = ForestFireDB()
    print("Database and table 'fires' are ready.")