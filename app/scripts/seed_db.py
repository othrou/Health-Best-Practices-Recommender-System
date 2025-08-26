import json
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from sentence_transformers import SentenceTransformer
import torch
import os
import sys

# Add the app directory to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config import get_settings

settings = get_settings()
DATA_FILE = os.path.join(os.path.dirname(__file__), '..', 'data', 'practices.json')
COLLECTION_NAME = "practices"

async def seed_database():
    """
    Reads holistic practices data, generates embeddings, and inserts them into MongoDB.
    """
    client = AsyncIOMotorClient(settings.MONGO_URI)
    db = client[settings.MONGO_DB_NAME]

    # 1. Check if the collection is already seeded
    if await db[COLLECTION_NAME].count_documents({}) > 0:
        print(f"Collection '{COLLECTION_NAME}' already contains documents. Seeding skipped.")
        return

    # 2. Load the raw data
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Error: Data file not found at {DATA_FILE}")
        return
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from {DATA_FILE}")
        return

    practices = data.get("practices", [])
    if not practices:
        print("No practices found in the data file.")
        return

    # 3. Load the embedding model
    print(f"Loading embedding model: {settings.EMBEDDING_MODEL_NAME}...")
    device = "cuda" if torch.cuda.is_available() else "cpu"
    embedding_model = SentenceTransformer(settings.EMBEDDING_MODEL_NAME, device=device)
    print("Model loaded successfully.")

    # 4. Process each practice
    processed_practices = []
    descriptions = [p.get("description", {}).get("full", "") for p in practices]
    
    print(f"Generating embeddings for {len(descriptions)} practices...")
    embeddings = embedding_model.encode(
        descriptions, 
        convert_to_tensor=True,
        show_progress_bar=True
    )
    print("Embeddings generated.")

    for i, practice in enumerate(practices):
        # Remove old, incompatible vectors
        if "search_vectors" in practice:
            del practice["search_vectors"]
        
        # Add new, correctly generated embedding
        practice["embedding"] = embeddings[i].cpu().tolist()
        processed_practices.append(practice)
        
    # 5. Insert into MongoDB
    if processed_practices:
        print(f"Inserting {len(processed_practices)} processed practices into MongoDB...")
        await db[COLLECTION_NAME].insert_many(processed_practices)
        print("Database seeding complete.")
    else:
        print("No practices were processed to be inserted.")

    client.close()

if __name__ == "__main__":
    asyncio.run(seed_database())