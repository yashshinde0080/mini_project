from pymongo import MongoClient
import os
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGODB_URI", "mongodb+srv://syash0080_db_user:yashshinde0080@mini-project.do1glvz.mongodb.net/?retryWrites=true&w=majority&ssl=true&ssl_cert_reqs=CERT_NONE")

print(f"Testing connection to: {MONGO_URI}")

try:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    client.server_info()
    print("SUCCESS: Connected to MongoDB Atlas!")
except Exception as e:
    print(f"FAILURE: Could not connect to MongoDB Atlas. Error: {e}")
