# tests/test_auth.py

import pytest
from fastapi.testclient import TestClient
from fastapi import Depends
from app.main import app
from app.api.routes.auth import get_current_user # Assuming this is where your dependency lives

# Constants for test user
TEST_USER_EMAIL = "testuser@example.com"
TEST_USER_PASSWORD = "a_secure_password"


def test_register_success(client: TestClient):
    """
    Test successful user registration.
    The 'client' fixture is automatically provided by conftest.py.
    """
    response = client.post(
        "/api/v1/auth/register",
        json={"email": TEST_USER_EMAIL, "password": TEST_USER_PASSWORD}
    )
    assert response.status_code == 201
    assert response.json() == {"message": "User created successfully"}

def test_register_duplicate_email(client: TestClient):
    """
    Test that registering with an already existing email fails.
    """
    # First, create the user
    client.post("/api/v1/auth/register", json={"email": TEST_USER_EMAIL, "password": TEST_USER_PASSWORD})
    
    # Then, try to create the same user again
    response = client.post(
        "/api/v1/auth/register",
        json={"email": TEST_USER_EMAIL, "password": "another_password"}
    )
    assert response.status_code == 400
    assert response.json() == {"detail": "Email already registered"}

def test_login_success(client: TestClient):
    """
    Test successful login and reception of an access token.
    """
    # Register the user first
    client.post("/api/v1/auth/register", json={"email": TEST_USER_EMAIL, "password": TEST_USER_PASSWORD})

    # Attempt to log in
    response = client.post(
        "/api/v1/auth/login",
        data={"username": TEST_USER_EMAIL, "password": TEST_USER_PASSWORD}
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert "holistic_refresh_token" in response.cookies

def test_login_invalid_credentials(client: TestClient):
    """
    Test login with incorrect password.
    """
    client.post("/api/v1/auth/register", json={"email": TEST_USER_EMAIL, "password": TEST_USER_PASSWORD})

    response = client.post(
        "/api/v1/auth/login",
        data={"username": TEST_USER_EMAIL, "password": "wrong_password"}
    )
    assert response.status_code == 401
    assert response.json() == {"detail": "Incorrect email or password"}

def test_refresh_token_success(client: TestClient):
    """
    Test that a new access token can be obtained using the refresh token cookie.
    """
    client.post("/api/v1/auth/register", json={"email": TEST_USER_EMAIL, "password": TEST_USER_PASSWORD})
    
    # Log in to get the refresh token cookie
    login_response = client.post(
        "/api/v1/auth/login",
        data={"username": TEST_USER_EMAIL, "password": TEST_USER_PASSWORD}
    )
    refresh_cookie = login_response.cookies.get("holistic_refresh_token")
    assert refresh_cookie is not None

    # Use the cookie to refresh the access token
    refresh_response = client.post(
        "/api/v1/auth/refresh",
        cookies={"holistic_refresh_token": refresh_cookie}
    )
    assert refresh_response.status_code == 200
    data = refresh_response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

def test_logout_success(client: TestClient):
    """
    Test that the logout endpoint clears the refresh token cookie.
    """
    client.post("/api/v1/auth/register", json={"email": TEST_USER_EMAIL, "password": TEST_USER_PASSWORD})
    login_response = client.post("/api/v1/auth/login", data={"username": TEST_USER_EMAIL, "password": TEST_USER_PASSWORD})
    
    logout_response = client.post("/api/v1/auth/logout", cookies=login_response.cookies)
    
    assert logout_response.status_code == 200


# Example of a protected route to test against
@app.get("/api/v1/test-protected")
async def protected_route_test(user=Depends(get_current_user)):
    return {"user_id": user["user_id"]}

def test_protected_route_with_valid_token(client: TestClient):
    """
    Test accessing a protected route with a valid JWT.
    """
    client.post("/api/v1/auth/register", json={"email": TEST_USER_EMAIL, "password": TEST_USER_PASSWORD})
    login_response = client.post("/api/v1/auth/login", data={"username": TEST_USER_EMAIL, "password": TEST_USER_PASSWORD})
    access_token = login_response.json()["access_token"]

    headers = {"Authorization": f"Bearer {access_token}"}
    response = client.get("/api/v1/test-protected", headers=headers)
    
    assert response.status_code == 200
    assert "user_id" in response.json()

def test_protected_route_without_token(client: TestClient):
    """
    Test that accessing a protected route without a token fails.
    """
    response = client.get("/api/v1/test-protected")
    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}
