from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
import os

load_dotenv()
MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = "Blogging"
COLLECTION_NAME = "users"
BOOK_COLLECTION = "books"

client = None

async def init_db():
    global client
    try:
        client = AsyncIOMotorClient(MONGO_URI)
        await client.admin.command('ping')
        print("Pinged your deployment. You successfully connected to MongoDB!")
    except Exception as e:
        print(f"Failed to connect to MongoDB: {e}")
        raise

async def close_db():
    global client
    if client:
        client.close()
        print("MongoDB connection closed.")

def get_collection():
    return client[DB_NAME][COLLECTION_NAME]


def get_book_collection():
    return client[DB_NAME][BOOK_COLLECTION]


