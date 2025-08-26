"""Ce fichier est un fichier spécial pour pytest. Il nous permet de définir des "fixtures", 
qui sont des fonctions préparant l'environnement de test (comme créer un client d'API ou une connexion à la base de données)."""

import pytest
import os
from fastapi.testclient import TestClient
from pymongo import MongoClient
 

# --- 1. Indiquer à l'application qu'elle est en mode test AVANT d'importer l'app ---
os.environ["TESTING"] = "True"


from app.main import app
from app.config import get_settings

@pytest.fixture(scope="session")
def db_connection():
    """
    Crée une connexion à la base de données de test pour la session de test.
    """
    settings = get_settings()
    client = MongoClient(settings.MONGO_URI)
    db = client[settings.MONGO_DB_NAME]
    
    # S'assure que la base de données est vide avant les tests
    for collection in db.list_collection_names():
        db[collection].delete_many({})
    
    yield client # Fournit le client aux tests
    
    # --- Teardown ---
    # Supprime la base de données de test après que tous les tests sont terminés
    print(f"\nDropping test database: {settings.MONGO_DB_NAME}")
    client.drop_database(settings.MONGO_DB_NAME)
    client.close()


@pytest.fixture(scope="module")
def client(db_connection):
    """
    Crée un client de test pour l'API FastAPI.
    Ce client sera partagé par tous les tests dans un même fichier.
    """
    with TestClient(app) as test_client:
        yield test_client
