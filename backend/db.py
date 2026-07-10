"""
Database initialisation for Jarvis.

Creates (if not already present) the SQLite tables used by the assistant:

- **sys_command**  : maps user-friendly app names to executable / shortcut paths.
- **web_command**  : maps user-friendly site names to URLs.
- **contacts**     : stores contact names, phone numbers, and email addresses.

The database file (``jarvis.db``) is created in the project root automatically
on the first import of this module.
"""

import os
import sqlite3

# -- Locate the database relative to this file's grandparent (project root) --
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(_ROOT, "jarvis.db")

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# 1. System commands (apps)
cursor.execute(
    """CREATE TABLE IF NOT EXISTS sys_command (
        id INTEGER PRIMARY KEY,
        name VARCHAR(100),
        path VARCHAR(1000)
    )"""
)

# 2. Website commands
cursor.execute(
    """CREATE TABLE IF NOT EXISTS web_command (
        id INTEGER PRIMARY KEY,
        name VARCHAR(100),
        url VARCHAR(1000)
    )"""
)

# 3. Contacts
cursor.execute(
    """CREATE TABLE IF NOT EXISTS contacts (
        id INTEGER PRIMARY KEY,
        name VARCHAR(200),
        Phone VARCHAR(255),
        email VARCHAR(255)
    )"""
)

conn.commit()

# -- Optionally import contacts from a CSV file at startup --
# Uncomment and adapt the block below if you have a contacts.csv to import.
#
# import csv
# DESIRED_COLUMNS = [0, 20]   # adjust to match your CSV structure
# csv_path = os.path.join(_ROOT, "contacts.csv")
# if os.path.exists(csv_path):
#     with open(csv_path, "r", encoding="utf-8") as f:
#         for row in csv.reader(f):
#             try:
#                 selected = [row[i] for i in DESIRED_COLUMNS]
#                 cursor.execute(
#                     "INSERT INTO contacts (id, name, Phone) VALUES (null, ?, ?)",
#                     tuple(selected),
#                 )
#             except (IndexError, ValueError):
#                 pass
#     conn.commit()
#     print("Contacts imported from contacts.csv")
