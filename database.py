import os
import json
import uuid
from datetime import datetime
from pymongo import MongoClient, errors as mongo_errors
from dotenv import load_dotenv
import streamlit as st

# Load environment variables from .env file
load_dotenv()

# -------------------- MongoDB Configuration --------------------
MONGO_URI = os.getenv("MONGODB_URI") or st.secrets.get("MONGODB_URI")
DB_NAME = os.getenv("MONGODB_DB") or st.secrets.get("MONGODB_DB")

# Clean up the connection string (remove quotes and whitespace if present)
if MONGO_URI:
    MONGO_URI = MONGO_URI.strip().strip('"').strip("'")
if DB_NAME:
    DB_NAME = DB_NAME.strip().strip('"').strip("'")

# -------------------- Database Setup --------------------
use_mongo = True
client = None
db = None
users_col = None
students_col = None
att_col = None
sessions_col = None
links_col = None

try:
    # Validate configuration exists
    if not MONGO_URI or not DB_NAME:
        raise ValueError("MONGODB_URI or MONGODB_DB not found in secrets/environment")

    # Increase timeout for production reliability and retry logic
    client = MongoClient(
        MONGO_URI,
        serverSelectionTimeoutMS=15000,
        connectTimeoutMS=15000,
        socketTimeoutMS=15000,
        retryWrites=True,
        w='majority'
    )

    # Force connection test - this will raise an exception if connection fails
    client.admin.command('ping')

    db = client[DB_NAME]
    users_col = db["users"]
    students_col = db["students"]
    att_col = db["attendance"]
    sessions_col = db["attendance_sessions"]
    links_col = db["attendance_links"]

    # Create indexes for user isolation and data integrity
    # Use background=True to avoid blocking on index creation
    try:
        # Users collection - unique username and email, plus user_id for referential integrity
        users_col.create_index("username", unique=True, background=True)
        users_col.create_index("user_id", unique=True, sparse=True, background=True)
        users_col.create_index("email", unique=True, sparse=True, background=True)
        users_col.create_index("password_reset_token", background=True)

        # Students collection - compound unique index on (student_id, created_by) for user isolation
        students_col.create_index([("student_id", 1), ("created_by", 1)], unique=True, background=True)
        students_col.create_index("created_by", background=True)

        # Attendance collection - compound unique index on (student_id, date, created_by) for user isolation
        att_col.create_index([("student_id", 1), ("date", 1), ("created_by", 1)], unique=True, background=True)
        att_col.create_index("created_by", background=True)
        att_col.create_index([("created_by", 1), ("date", 1)], background=True)

        # Sessions and links collections
        sessions_col.create_index("session_id", unique=True, background=True)
        sessions_col.create_index("created_by", background=True)
        sessions_col.create_index("expires_at", expireAfterSeconds=0, background=True)
        links_col.create_index("link_id", unique=True, background=True)
        links_col.create_index("created_by", background=True)
        links_col.create_index("expires_at", expireAfterSeconds=0, background=True)
    except Exception as idx_error:
        # Index creation failures are non-critical (indexes may already exist)
        print(f"Index note: {idx_error}")

    print("✅ MongoDB connected successfully")

except mongo_errors.ServerSelectionTimeoutError as e:
    # This is the error you're getting - MongoDB server not reachable
    error_msg = str(e)
    print(f"\n{'=' * 80}")
    print("❌ MongoDB Connection Timeout")
    print(f"{'=' * 80}")
    print(f"Error: {error_msg}")
    print("\n🔧 SOLUTION:")
    print("1. Go to MongoDB Atlas → Network Access")
    print("2. Click 'Add IP Address'")
    print("3. Select 'Allow Access from Anywhere' (0.0.0.0/0)")
    print("4. This is required for Streamlit Cloud's dynamic IPs")
    print(f"\n{'=' * 80}\n")

    # Check if running locally
    is_local = os.path.exists('.env')
    if is_local:
        print("⚠️  Running locally with JSON fallback")
        use_mongo = False
    else:
        raise RuntimeError(
            "MongoDB connection timeout in production. "
            "Add 0.0.0.0/0 to MongoDB Atlas Network Access whitelist."
        )

except mongo_errors.OperationFailure as e:
    # Authentication error - wrong credentials
    print(f"\n{'=' * 80}")
    print("❌ MongoDB Authentication Failed")
    print(f"{'=' * 80}")
    print(f"Error: {str(e)}")
    print("\n🔧 SOLUTION:")
    print("1. Check your MONGODB_URI username and password")
    print("2. MongoDB Atlas → Database Access → Verify user credentials")
    print(f"\n{'=' * 80}\n")

    is_local = os.path.exists('.env')
    if is_local:
        print("⚠️  Running locally with JSON fallback")
        use_mongo = False
    else:
        raise RuntimeError("MongoDB authentication failed in production. Check credentials.")

except mongo_errors.ConfigurationError as e:
    # Malformed connection string
    print(f"\n{'=' * 80}")
    print("❌ MongoDB Configuration Error")
    print(f"{'=' * 80}")
    print(f"Error: {str(e)}")
    print("\n🔧 SOLUTION:")
    print("Check your MONGODB_URI format in secrets")
    print("Should be: mongodb+srv://username:password@cluster.mongodb.net/")
    print(f"\n{'=' * 80}\n")

    is_local = os.path.exists('.env')
    if is_local:
        print("⚠️  Running locally with JSON fallback")
        use_mongo = False
    else:
        raise RuntimeError("MongoDB URI configuration error. Check connection string format.")

except ValueError as e:
    # Missing configuration
    print(f"\n{'=' * 80}")
    print("❌ Missing MongoDB Configuration")
    print(f"{'=' * 80}")
    print(f"Error: {str(e)}")
    print("\n🔧 SOLUTION:")
    print("Add these to Streamlit Cloud Settings → Secrets:")
    print('MONGODB_URI = "mongodb+srv://user:pass@cluster.mongodb.net/"')
    print('MONGODB_DB = "your_database_name"')
    print(f"\n{'=' * 80}\n")

    is_local = os.path.exists('.env')
    if is_local:
        print("⚠️  Running locally with JSON fallback")
        use_mongo = False
    else:
        raise RuntimeError("MongoDB configuration missing. Add MONGODB_URI and MONGODB_DB to secrets.")

except Exception as e:
    # Unexpected error
    error_msg = f"{type(e).__name__}: {str(e)}"
    print(f"\n{'=' * 80}")
    print("❌ Unexpected MongoDB Error")
    print(f"{'=' * 80}")
    print(f"Error: {error_msg}")
    print(f"\n{'=' * 80}\n")

    is_local = os.path.exists('.env')
    if is_local:
        print("⚠️  Running locally with JSON fallback")
        use_mongo = False
    else:
        raise RuntimeError(f"Unexpected database error: {error_msg}")

# -------------------- JSON Fallback for Local Development --------------------
if not use_mongo:
    print("🔄 Initializing local JSON storage (development mode)")
    data_dir = os.path.join(os.path.dirname(__file__), "data")
    os.makedirs(data_dir, exist_ok=True)
    USERS_FILE = os.path.join(data_dir, "users.json")
    STUDENTS_FILE = os.path.join(data_dir, "students.json")
    ATT_FILE = os.path.join(data_dir, "attendance.json")
    SESSIONS_FILE = os.path.join(data_dir, "sessions.json")
    LINKS_FILE = os.path.join(data_dir, "links.json")

    for f in (USERS_FILE, STUDENTS_FILE, ATT_FILE, SESSIONS_FILE, LINKS_FILE):
        if not os.path.exists(f):
            with open(f, "w") as fh:
                json.dump([], fh)


    class SimpleCol:
        def __init__(self, path):
            self.path = path

        def _load(self):
            try:
                with open(self.path, "r") as fh:
                    data = json.load(fh)
                if self.path.endswith(("sessions.json", "links.json")):
                    now = datetime.now().isoformat()
                    data = [d for d in data if d.get("expires_at", "9999-12-31") > now]
                    self._save(data)
                return data
            except (FileNotFoundError, json.JSONDecodeError):
                return []

        def _save(self, data):
            with open(self.path, "w") as fh:
                json.dump(data, fh, default=str, indent=2)

        def find_one(self, filt):
            data = self._load()
            for d in data:
                ok = True
                for k, v in (filt or {}).items():
                    if d.get(k) != v:
                        ok = False
                        break
                if ok:
                    return d
            return None

        def find(self, filt=None):
            data = self._load()
            if not filt:
                return data
            out = []
            for d in data:
                ok = True
                for k, v in filt.items():
                    if d.get(k) != v:
                        ok = False
                        break
                if ok:
                    out.append(d)
            return out

        def insert_one(self, doc):
            data = self._load()
            data.append(doc)
            self._save(data)
            return {"inserted_id": len(data)}

        def update_one(self, filt, update, upsert=False):
            data = self._load()
            found = False
            for i, d in enumerate(data):
                ok = True
                for k, v in filt.items():
                    if d.get(k) != v:
                        ok = False
                        break
                if ok:
                    if "$set" in update:
                        for kk, vv in update["$set"].items():
                            d[kk] = vv
                    data[i] = d
                    found = True
                    break
            if not found and upsert:
                new = dict(filt)
                if "$set" in update:
                    new.update(update["$set"])
                data.append(new)
            self._save(data)

        def update_many(self, filt, update):
            data = self._load()
            modified_count = 0
            for i, d in enumerate(data):
                ok = True
                for k, v in filt.items():
                    if isinstance(v, dict) and "$exists" in v:
                        if v["$exists"] and k not in d:
                            ok = False
                        elif not v["$exists"] and k in d:
                            ok = False
                    elif d.get(k) != v:
                        ok = False
                        break
                if ok:
                    if "$set" in update:
                        for kk, vv in update["$set"].items():
                            d[kk] = vv
                    data[i] = d
                    modified_count += 1
            self._save(data)
            return type('obj', (object,), {'modified_count': modified_count})()

        def delete_many(self, filt):
            data = self._load()
            out = []
            removed = 0
            for d in data:
                match = True
                for k, v in (filt or {}).items():
                    if d.get(k) != v:
                        match = False
                        break
                if not match:
                    out.append(d)
                else:
                    removed += 1
            self._save(out)
            return {"deleted_count": removed}

        def count_documents(self, filt=None):
            return len(self.find(filt))


    users_col = SimpleCol(USERS_FILE)
    students_col = SimpleCol(STUDENTS_FILE)
    att_col = SimpleCol(ATT_FILE)
    sessions_col = SimpleCol(SESSIONS_FILE)
    links_col = SimpleCol(LINKS_FILE)


# -------------------- Helper Functions --------------------
def generate_user_id():
    """Generate a unique user ID"""
    return str(uuid.uuid4())


# -------------------- Data Migration for User Isolation --------------------
def migrate_users_add_user_id():
    """Migration to add user_id field to existing users"""
    try:
        if use_mongo:
            # MongoDB mode: add user_id to users without one
            users_without_id = list(users_col.find({"user_id": {"$exists": False}}))
            for user in users_without_id:
                users_col.update_one(
                    {"username": user["username"]},
                    {"$set": {"user_id": generate_user_id()}}
                )
            if users_without_id:
                print(f"Migration: Added user_id to {len(users_without_id)} users")
        else:
            # JSON mode
            users_data = users_col._load()
            updated = 0
            for user in users_data:
                if "user_id" not in user:
                    user["user_id"] = generate_user_id()
                    updated += 1
            if updated > 0:
                users_col._save(users_data)
                print(f"Migration: Added user_id to {updated} users")
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

        if use_mongo:
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
        else:
            # JSON mode: iterate and update documents manually
            students_count = 0
            students_data = students_col._load()
            for doc in students_data:
                if "created_by" not in doc:
                    doc["created_by"] = default_user
                    students_count += 1
            if students_count > 0:
                students_col._save(students_data)

            att_count = 0
            att_data = att_col._load()
            for doc in att_data:
                if "created_by" not in doc:
                    doc["created_by"] = default_user
                    att_count += 1
            if att_count > 0:
                att_col._save(att_data)

            sessions_count = 0
            sessions_data = sessions_col._load()
            for doc in sessions_data:
                if "created_by" not in doc:
                    doc["created_by"] = default_user
                    sessions_count += 1
            if sessions_count > 0:
                sessions_col._save(sessions_data)

            links_count = 0
            links_data = links_col._load()
            for doc in links_data:
                if "created_by" not in doc:
                    doc["created_by"] = default_user
                    links_count += 1
            if links_count > 0:
                links_col._save(links_data)

            print(f"Migration completed: {students_count} students, {att_count} attendance records, "
                  f"{sessions_count} sessions, {links_count} links updated")

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
        'use_mongo': use_mongo
    }


# -------------------- Database Status Check --------------------
def get_database_status():
    """
    Get current database connection status.
    Returns connection info for debugging.
    """
    status = {
        'connected': use_mongo,
        'type': 'MongoDB' if use_mongo else 'JSON (ephemeral)',
        'database': DB_NAME if use_mongo else 'local files',
        'persistent': use_mongo
    }

    if use_mongo:
        try:
            # Test if we can actually query
            users_col.find_one({"_test": "connection"})
            status['query_test'] = 'OK'
        except Exception as e:
            status['query_test'] = f'FAILED: {str(e)}'
            status['persistent'] = False

    return status