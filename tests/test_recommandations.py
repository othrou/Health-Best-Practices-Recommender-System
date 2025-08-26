from fastapi.testclient import TestClient
from unittest import mock

BASE_URL = "http://localhost:8000/api/v1"



def test_recommendation_free_text_empty(client:TestClient):
        
        response = client.post(f"{BASE_URL}/recommendations/free-text", json={
            "session_id": "test_session_123",
            "text": ""  # Texte vide
        })

        assert response.status_code == 400  # Validation error (Texte vide)
