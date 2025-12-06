import os
import json
import uuid
from datetime import datetime
from pymongo import MongoClient, errors as mongo_errors
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# -------------------- MongoDB Configuration --------------------
MONGO_URI = os.getenv("MONGODB_URI","mongodb+srv://syash0080_db_user:yashshinde0080@mini-project.do1glvz.mongodb.net/?retryWrites=true&w=majority&ssl=true&ssl_cert_reqs=CERT_NONE")
DB_NAME = os.getenv("MONGODB_DB","smart_attendance_enhanced")

# -------------------- Database Setup --------------------
# -------------------- Database Setup --------------------
use_mongo = True
mongo_error_msg = None

try:
    # Increase timeout to 10 seconds for slower connections (e.g. Streamlit Cloud)
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=10000)
    
    # Trigger a connection to verify
    client.server_info()
    
    db = client[DB_NAME]
    users_col = db["users"]
    students_col = db["students"]
    att_col = db["attendance"]
    sessions_col = db["attendance_sessions"]
    links_col = db["attendance_links"]

    # Create indexes for user isolation and data integrity
    # Users collection - unique username and email, plus user_id for referential integrity
    users_col.create_index("username", unique=True)
    users_col.create_index("user_id", unique=True, sparse=True)
    users_col.create_index("email", unique=True, sparse=True)
    users_col.create_index("password_reset_token")

    # Students collection - compound unique index on (student_id, created_by) for user isolation
    # This allows different users to have students with the same student_id
    students_col.create_index([("student_id", 1), ("created_by", 1)], unique=True)
    students_col.create_index("created_by")  # Index for efficient user-filtered queries

    # Attendance collection - compound unique index on (student_id, date, created_by) for user isolation
    # This allows different users to mark attendance for students with the same ID
    att_col.create_index([("student_id", 1), ("date", 1), ("created_by", 1)], unique=True)
    att_col.create_index("created_by")  # Index for efficient user-filtered queries
    att_col.create_index([("created_by", 1), ("date", 1)])  # Compound index for date range queries

    # Sessions and links collections
    sessions_col.create_index("session_id", unique=True)
    sessions_col.create_index("created_by")
    sessions_col.create_index("expires_at", expireAfterSeconds=0)
    links_col.create_index("link_id", unique=True)
    links_col.create_index("created_by")
    links_col.create_index("expires_at", expireAfterSeconds=0)
    
    print("SUCCESS: Connected to MongoDB Atlas")

except Exception as e:
    # CRITICAL: We do NOT fall back to local files anymore.
    # We must inform the user that the connection failed.
    import streamlit as st
    st.error(f"❌ **CRITICAL ERROR: Could not connect to MongoDB Atlas.**\n\nThe application cannot start because it requires a persistent database connection.\n\nError details: {e}")
    st.stop()

# -------------------- Helper Functions --------------------
def generate_user_id():
    """Generate a unique user ID"""
    return str(uuid.uuid4())


# -------------------- Data Migration for User Isolation --------------------
def migrate_users_add_user_id():
    """Migration to add user_id field to existing users"""
    try:
        # MongoDB mode: add user_id to users without one
        users_without_id = list(users_col.find({"user_id": {"$exists": False}}))
        for user in users_without_id:
            users_col.update_one(
                {"username": user["username"]},
                {"$set": {"user_id": generate_user_id()}}
            )
        if users_without_id:
            print(f"Migration: Added user_id to {len(users_without_id)} users")
    except Exception as e:
        print(f"User ID migration error (non-critical): {e}")


def migrate_existing_data_to_user_ownership():
    """One-time migration to add created_by field to existing records"""
    try:
        # First, ensure all users have user_id
        migrate_users_add_user_id()

        # Find a default user to assign existing data to
        admin_user = users_col.find_one({"role": "admin"})
        if admin_user:
            default_user = admin_user["username"]
        else:
            first_user = users_col.find_one({})
            if not first_user:
                print("Migration skipped: No users found in database")
                return
            default_user = first_user["username"]

        print(f"Running data migration: assigning unowned data to '{default_user}'")

        # MongoDB mode: use update_many with $exists operator
        students_updated = students_col.update_many(
            {"created_by": {"$exists": False}},
            {"$set": {"created_by": default_user}}
        )
        att_updated = att_col.update_many(
            {"created_by": {"$exists": False}},
            {"$set": {"created_by": default_user}}
        )
        sessions_updated = sessions_col.update_many(
            {"created_by": {"$exists": False}},
            {"$set": {"created_by": default_user}}
        )
        links_updated = links_col.update_many(
            {"created_by": {"$exists": False}},
            {"$set": {"created_by": default_user}}
        )

        print(f"Migration completed: {students_updated.modified_count} students, "
              f"{att_updated.modified_count} attendance records, "
              f"{sessions_updated.modified_count} sessions, "
              f"{links_updated.modified_count} links updated")

    except Exception as e:
        print(f"Migration error (non-critical): {e}")


def get_collections():
    """Return all database collections"""
    return {
        'users': users_col,
        'students': students_col,
        'attendance': att_col,
        'sessions': sessions_col,
        'links': links_col,
        'use_mongo': True,
        'mongo_error': None
    }
