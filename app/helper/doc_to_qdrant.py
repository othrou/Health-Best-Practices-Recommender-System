import os
import tempfile
from typing import List

import bs4
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams
from langchain_core.embeddings import Embeddings
from langchain_community.document_loaders import PyPDFLoader, WebBaseLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_qdrant import QdrantVectorStore

import google.generativeai as genai


class GeminiEmbedder(Embeddings):
    """Embedding class using Google Gemini API."""
    def __init__(self, model_name: str, api_key: str):
        genai.configure(api_key=api_key)
        self.model = model_name

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return genai.embed_content(model=self.model, content=texts, task_type="retrieval_document")['embedding']

    def embed_query(self, text: str) -> List[float]:
        return genai.embed_content(model=self.model, content=text, task_type="retrieval_query")['embedding']


def get_qdrant_client(url: str, api_key: str) -> QdrantClient:
    """Initialize Qdrant client."""
    if not all([url, api_key]):
        raise ValueError("Qdrant URL and API key are required.")
    return QdrantClient(url=url, api_key=api_key, timeout=60, check_compatibility=False)


def process_pdf(file_path: str) -> List:
    """Process local PDF file and split into chunks."""
    loader = PyPDFLoader(file_path)
    docs = loader.load()
    for doc in docs:
        doc.metadata.update({"source_type": "pdf", "file_name": os.path.basename(file_path)})
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    return text_splitter.split_documents(docs)


def process_web(url: str) -> List:
    """Process web page content and split into chunks."""
    loader = WebBaseLoader(
        web_paths=(url,),
        bs_kwargs=dict(parse_only=bs4.SoupStrainer(class_=("post-content", "post-title", "post-header", "content", "main")))
    )
    docs = loader.load()
    for doc in docs:
        doc.metadata.update({"source_type": "url", "url": url})
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    return text_splitter.split_documents(docs)


def add_documents_to_store(client, documents, collection_name, embedding_model, google_api_key):
    """Create Qdrant collection if needed and add documents with embeddings."""
    try:
        client.get_collection(collection_name=collection_name)
    except Exception:
        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=768, distance=Distance.COSINE)
        )
        print(f"📚 Created new collection: {collection_name}")

    vector_store = QdrantVectorStore(
        client=client,
        collection_name=collection_name,
        embedding=GeminiEmbedder(model_name=embedding_model, api_key=google_api_key)
    )
    print("📤 Uploading documents to Qdrant...")
    vector_store.add_documents(documents)
    print("✅ Documents stored successfully!")
    return vector_store


if __name__ == "__main__":
    # Configs - replace with your real values
    QDRANT_URL = "https://316fe9ae-89c9-4968-819e-bba270fd2f0d.eu-central-1-0.aws.cloud.qdrant.io:6333"
    QDRANT_API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhY2Nlc3MiOiJtIn0.AHq4hiWn3oTeFM0A__lBkBAoQG8OMNKVaCOjYwR1_ns"
    GOOGLE_API_KEY = "AIzaSyDcYm0hn5ufycwvR17_-B9T6DDEBT67w3w"
    EMBEDDING_MODEL = "text-embedding-004"  
    COLLECTION_NAME = "Holilib"

    # Example usage:
    client = get_qdrant_client(QDRANT_URL, QDRANT_API_KEY)

    # 1. Process PDF file
    pdf_path = "path/to/your/document.pdf"
    pdf_docs = process_pdf(pdf_path)

    # OR

    # 2. Process Web URL
    # url = "https://example.com/article"
    # pdf_docs = process_web(url)

    # Add docs to Qdrant
    add_documents_to_store(client, pdf_docs, COLLECTION_NAME, EMBEDDING_MODEL, GOOGLE_API_KEY)
