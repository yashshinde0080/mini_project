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

# -------------------- Initialize ALL Variables First --------------------
# CRITICAL: Define these BEFORE try/except so they're always available for import
use_mongo = False
client = None
db = None
users_col = None
students_col = None
att_col = None
sessions_col = None
links_col = None


# -------------------- Helper Class for JSON Fallback --------------------
class SimpleCol:
    def __init__(self, path):
        self.path = path
        self.name = os.path.basename(path).replace('.json', '')

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
        print(f"⚠️  JSON WRITE: {self.name} - {len(data)} documents (EPHEMERAL - WILL BE LOST!)")

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
        print(f"⚠️  JSON INSERT: {self.name} - Document added (NOT PERSISTENT)")
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
        print(f"⚠️  JSON UPDATE: {self.name} - Document updated (NOT PERSISTENT)")

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
        print(f"⚠️  JSON UPDATE MANY: {self.name} - {modified_count} documents updated (NOT PERSISTENT)")
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
        print(f"⚠️  JSON DELETE: {self.name} - {removed} documents deleted (NOT PERSISTENT)")
        return {"deleted_count": removed}

    def count_documents(self, filt=None):
        return len(self.find(filt))


# -------------------- Database Connection Logic --------------------
def initialize_database():
    """Initialize database connection - returns True if MongoDB, False if local JSON"""
    global use_mongo, client, db, users_col, students_col, att_col, sessions_col, links_col

    try:
        # Validate configuration exists
        if not MONGO_URI or not DB_NAME:
            raise ValueError("MONGODB_URI or MONGODB_DB not found in secrets/environment")

        # Connection with SSL/TLS fix for Streamlit Cloud
        client = MongoClient(
            MONGO_URI,
            serverSelectionTimeoutMS=20000,
            connectTimeoutMS=20000,
            socketTimeoutMS=20000,
            retryWrites=True,
            w='majority',
            tls=True,
            tlsAllowInvalidCertificates=True
        )

        # Force connection test
        client.admin.command('ping')

        db = client[DB_NAME]
        users_col = db["users"]
        students_col = db["students"]
        att_col = db["attendance"]
        sessions_col = db["attendance_sessions"]
        links_col = db["attendance_links"]

        # Create indexes
        try:
            users_col.create_index("username", unique=True, background=True)
            users_col.create_index("user_id", unique=True, sparse=True, background=True)
            users_col.create_index("email", unique=True, sparse=True, background=True)
            users_col.create_index("password_reset_token", background=True)
            students_col.create_index([("student_id", 1), ("created_by", 1)], unique=True, background=True)
            students_col.create_index("created_by", background=True)
            att_col.create_index([("student_id", 1), ("date", 1), ("created_by", 1)], unique=True, background=True)
            att_col.create_index("created_by", background=True)
            att_col.create_index([("created_by", 1), ("date", 1)], background=True)
            sessions_col.create_index("session_id", unique=True, background=True)
            sessions_col.create_index("created_by", background=True)
            sessions_col.create_index("expires_at", expireAfterSeconds=0, background=True)
            links_col.create_index("link_id", unique=True, background=True)
            links_col.create_index("created_by", background=True)
            links_col.create_index("expires_at", expireAfterSeconds=0, background=True)
        except Exception as idx_error:
            print(f"Index creation note: {idx_error}")

        use_mongo = True
        print("✅ MongoDB connected successfully")
        print(f"📊 Database: {DB_NAME}")
        print(f"🔗 Cluster: {MONGO_URI.split('@')[1].split('/')[0] if '@' in MONGO_URI else 'unknown'}")

        # FORCE a test write to verify it's actually working
        try:
            test_result = users_col.insert_one({
                "_test_connection": True,
                "timestamp": datetime.now(),
                "message": "MongoDB write test successful"
            })
            print(f"✅ Write test successful - inserted ID: {test_result.inserted_id}")

            # Verify we can read it back
            found = users_col.find_one({"_test_connection": True})
            if found:
                print(f"✅ Read test successful - found document")
                # Clean up test document
                users_col.delete_one({"_test_connection": True})
                print(f"✅ Delete test successful")
            else:
                print("❌ WARNING: Could not read back test document!")

        except Exception as test_error:
            print(f"❌ WARNING: Write/Read test failed: {test_error}")

        return True

    except Exception as e:
        error_type = type(e).__name__
        error_msg = str(e)

        print(f"\n{'=' * 80}")
        print(f"❌ MongoDB Connection Failed: {error_type}")
        print(f"{'=' * 80}")
        print(f"Error: {error_msg}")

        if "SSL" in error_msg or "TLS" in error_msg:
            print("\n🔧 SSL/TLS Error - Update your connection string:")
            print("Add to your MONGODB_URI: ?ssl=true&ssl_cert_reqs=CERT_NONE")
        elif "ServerSelectionTimeout" in error_type:
            print("\n🔧 Connection Timeout - Check:")
            print("1. MongoDB Atlas → Network Access → Add 0.0.0.0/0")
            print("2. Cluster is not paused")
        elif "OperationFailure" in error_type or "Authentication" in error_msg:
            print("\n🔧 Authentication Error - Check credentials in MONGODB_URI")

        print(f"\n{'=' * 80}\n")
        return False


# Try to connect to MongoDB
mongodb_connected = initialize_database()

# If MongoDB failed, initialize JSON fallback
if not mongodb_connected:
    is_local = os.path.exists('.env')

    if not is_local:
        print("⚠️  WARNING: Running in PRODUCTION without persistent database!")
        print("⚠️  All data will be LOST on app restart!")
        print("⚠️  Fix MongoDB connection for data persistence!")

    print("🔄 Initializing local JSON storage (ephemeral)")
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

    users_col = SimpleCol(USERS_FILE)
    students_col = SimpleCol(STUDENTS_FILE)
    att_col = SimpleCol(ATT_FILE)
    sessions_col = SimpleCol(SESSIONS_FILE)
    links_col = SimpleCol(LINKS_FILE)
    use_mongo = False


# -------------------- Helper Functions --------------------
def generate_user_id():
    """Generate a unique user ID"""
    return str(uuid.uuid4())


# -------------------- Data Migration for User Isolation --------------------
def migrate_users_add_user_id():
    """Migration to add user_id field to existing users"""
    try:
        if use_mongo:
            users_without_id = list(users_col.find({"user_id": {"$exists": False}}))
            for user in users_without_id:
                users_col.update_one(
                    {"username": user["username"]},
                    {"$set": {"user_id": generate_user_id()}}
                )
            if users_without_id:
                print(f"Migration: Added user_id to {len(users_without_id)} users")
        else:
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
        migrate_users_add_user_id()

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


def get_database_status():
    """Get current database connection status"""
    status = {
        'connected': use_mongo,
        'type': 'MongoDB' if use_mongo else 'JSON (ephemeral)',
        'database': DB_NAME if use_mongo else 'local files',
        'persistent': use_mongo
    }

    if use_mongo and users_col:
        try:
            # Test read
            users_col.find_one({"_test": "connection"})
            status['query_test'] = 'OK'

            # Get actual document counts
            status['user_count'] = users_col.count_documents({})
            status['student_count'] = students_col.count_documents({})
            status['attendance_count'] = att_col.count_documents({})

            # Test write
            test_doc = {"_test": "write_check", "timestamp": datetime.now()}
            users_col.insert_one(test_doc)
            users_col.delete_many({"_test": "write_check"})
            status['write_test'] = 'OK'

        except Exception as e:
            status['query_test'] = f'FAILED: {str(e)}'
            status['persistent'] = False

    return status


def verify_data_write(collection_name, username=None):
    """
    Verify data is actually being written to MongoDB.
    Call this after any create/update operation to debug.
    """
    if not use_mongo:
        return {"error": "Not using MongoDB"}

    try:
        col = {
            'users': users_col,
            'students': students_col,
            'attendance': att_col,
            'sessions': sessions_col,
            'links': links_col
        }.get(collection_name)

        if not col:
            return {"error": f"Invalid collection: {collection_name}"}

        # Count total documents
        total = col.count_documents({})

        # If username provided, count user-specific documents
        user_specific = None
        if username and collection_name != 'users':
            user_specific = col.count_documents({"created_by": username})

        # Get sample document
        sample = col.find_one({})

        return {
            "collection": collection_name,
            "database": DB_NAME,
            "total_documents": total,
            "user_documents": user_specific,
            "sample_doc": sample,
            "mongodb_connected": use_mongo
        }
    except Exception as e:
        return {"error": str(e)}