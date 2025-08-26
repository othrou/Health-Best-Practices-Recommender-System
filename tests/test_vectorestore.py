import logging
import asyncio
from typing import List, Dict, Any

import google.generativeai as genai
from qdrant_client import QdrantClient
from langchain_core.embeddings import Embeddings
from langchain_qdrant import QdrantVectorStore
from agno.agent import Agent
from agno.models.google import Gemini
from langchain_core.documents import Document
from langchain.retrievers import EnsembleRetriever,BM25Retriever
#from langchain_community.retrievers import BM25Retriever

from app.config import Settings


logger = logging.getLogger(__name__)

settings = Settings()

def test_qdrant_connection():
    """
    Teste la connexion à Qdrant et l'initialisation du Vector Store.
    """
    try:
        # Initialiser le client Qdrant
        qdrant_client = QdrantClient(
            url=settings.QDRANT_URL, 
            api_key=settings.QDRANT_API_KEY,
            timeout=60
        )
        logger.info("✅ Connecté à Qdrant.")
    except Exception as e:
        logger.error(f"🔴 Échec de la connexion à Qdrant : {e}")
        return

    # Vérifier si la collection existe
    try:
        qdrant_client.get_collection(collection_name=settings.QDRANT_COLLECTION_NAME)
        logger.info("Collection trouvée.")
    except Exception as e:
        logger.error(f"🔴 La collection '{settings.QDRANT_COLLECTION_NAME}' est introuvable : {e}")
        return



