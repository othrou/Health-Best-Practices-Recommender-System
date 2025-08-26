from motor.motor_asyncio import AsyncIOMotorClient
from app.config import get_settings

settings = get_settings()

class Database:
    client: AsyncIOMotorClient = None

db = Database()

async def get_database() -> AsyncIOMotorClient:
    return db.client[settings.MONGO_DB_NAME]

async def connect_to_mongo():
    print("Connecting to MongoDB...")
    db.client = AsyncIOMotorClient(settings.MONGO_URI)
    print("Successfully connected to MongoDB.")

async def close_mongo_connection():
    print("Closing MongoDB connection.")
    db.client.close()
    print("MongoDB connection closed.")