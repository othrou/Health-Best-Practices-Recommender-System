from fastapi.testclient import TestClient

def test_read_root(client: TestClient):
    """
    Teste si l'endpoint racine ("/") fonctionne correctement.
    """
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Welcome to the Holistic AI Recommender API."}

def test_questionnaire_loading(client: TestClient):
    """
    Teste si l'endpoint pour charger le questionnaire fonctionne correctement.
    """
    response = client.get("/api/v1/questionnaire/config")
    assert response.status_code == 200
    data = response.json()
    assert len(data) > 0  

def test_create_feedback(client):
    # Test submitting feedback via the API

    feedback_data = {
        "session_id": "session_123",
        "rating": 5,
        "comment": "Excellent service, highly recommend!"
    }

    # Sending POST request to /api/v1/feedback
    response = client.post("/api/v1/feedback/", json=feedback_data)

    
    assert response.status_code == 201 # Created
    assert response.json() == {"message": "Feedback reçu avec succès"}



def test_submit_feedback_invalid_rating(client: TestClient):
    """
    Teste l'envoi d'un feedback avec une note invalide (ex: 6).
    """
    feedback_payload = {
        "session_id": "test_session_456",
        "practice_name": "Test Practice",
        "rating": 6, # Note invalide
        "comments": "Invalid rating."
    }
    
    response = client.post("/api/v1/feedback/", json=feedback_payload)
    
    # Vérifie que l'API rejette la requête avec une erreur 422 (Unprocessable Entity)
    assert response.status_code == 422

