"""
Integration test for authentication system.

Tests the full authentication flow via API.
"""
import requests
import time

# API base URL
API_URL = "http://localhost:8000"

def print_section(title):
    """Print section header."""
    print("\n" + "=" * 60)
    print(title)
    print("=" * 60)

def test_user_registration():
    """Test user registration."""
    print_section("TEST 1: User Registration")

    response = requests.post(
        f"{API_URL}/auth/register",
        json={
            "email": f"testuser_{int(time.time())}@example.com",
            "password": "TestPassword123",
            "name": "Integration Test User",
            "tenant_id": "tenant_integration"
        }
    )

    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.json()}")

    assert response.status_code == 201, "Registration failed"
    data = response.json()
    assert "user_id" in data, "user_id not in response"
    assert "email" in data, "email not in response"

    print("✓ User registration successful!")
    return data["email"]

def test_login(email):
    """Test login."""
    print_section("TEST 2: Login")

    response = requests.post(
        f"{API_URL}/auth/login",
        json={
            "email": email,
            "password": "TestPassword123"
        }
    )

    print(f"Status Code: {response.status_code}")
    data = response.json()
    print(f"Response: {data}")

    assert response.status_code == 200, "Login failed"
    assert "access_token" in data, "access_token not in response"
    assert "refresh_token" in data, "refresh_token not in response"
    assert data["requires_2fa"] == False, "2FA should not be required"

    print("✓ Login successful!")
    return data["access_token"], data.get("session_id")

def test_get_user_profile(token):
    """Test getting user profile."""
    print_section("TEST 3: Get User Profile")

    response = requests.get(
        f"{API_URL}/auth/me",
        headers={"Authorization": f"Bearer {token}"}
    )

    print(f"Status Code: {response.status_code}")
    data = response.json()
    print(f"Response: {data}")

    assert response.status_code == 200, "Get profile failed"
    assert "user_id" in data, "user_id not in response"
    assert "email" in data, "email not in response"
    assert "roles" in data, "roles not in response"

    print("✓ Get user profile successful!")
    return data

def test_get_sessions(token):
    """Test getting active sessions."""
    print_section("TEST 4: Get Active Sessions")

    response = requests.get(
        f"{API_URL}/auth/sessions",
        headers={"Authorization": f"Bearer {token}"}
    )

    print(f"Status Code: {response.status_code}")
    data = response.json()
    print(f"Response (sessions count): {len(data)}")

    assert response.status_code == 200, "Get sessions failed"
    assert isinstance(data, list), "Response should be a list"

    if data:
        print(f"  Session 1:")
        print(f"    - Device: {data[0].get('device_name', 'Unknown')}")
        print(f"    - OS: {data[0].get('os', 'Unknown')}")
        print(f"    - Browser: {data[0].get('browser', 'Unknown')}")
        print(f"    - Current: {data[0].get('is_current', False)}")

    print("✓ Get sessions successful!")
    return data

def test_2fa_status(token):
    """Test 2FA status check."""
    print_section("TEST 5: Check 2FA Status")

    response = requests.get(
        f"{API_URL}/auth/2fa/status",
        headers={"Authorization": f"Bearer {token}"}
    )

    print(f"Status Code: {response.status_code}")
    data = response.json()
    print(f"Response: {data}")

    assert response.status_code == 200, "Get 2FA status failed"
    assert "enabled" in data, "enabled not in response"

    print("✓ 2FA status check successful!")
    return data

def test_logout(token, session_id):
    """Test logout."""
    print_section("TEST 6: Logout")

    headers = {"Authorization": f"Bearer {token}"}
    if session_id:
        headers["X-Session-ID"] = session_id

    response = requests.post(
        f"{API_URL}/auth/logout",
        headers=headers
    )

    print(f"Status Code: {response.status_code}")
    data = response.json()
    print(f"Response: {data}")

    assert response.status_code == 200, "Logout failed"

    print("✓ Logout successful!")

def test_openapi_docs():
    """Test OpenAPI documentation availability."""
    print_section("TEST 7: OpenAPI Documentation")

    response = requests.get(f"{API_URL}/openapi.json")

    print(f"Status Code: {response.status_code}")
    data = response.json()
    print(f"OpenAPI Version: {data.get('openapi', 'Unknown')}")
    print(f"API Title: {data.get('info', {}).get('title', 'Unknown')}")
    print(f"API Version: {data.get('info', {}).get('version', 'Unknown')}")
    print(f"Endpoints: {len(data.get('paths', {}))}")

    assert response.status_code == 200, "Get OpenAPI spec failed"
    assert "openapi" in data, "openapi field not in response"

    print("✓ OpenAPI documentation available!")

def main():
    """Run all integration tests."""
    print("\n" + "=" * 60)
    print("AUTHENTICATION SYSTEM - INTEGRATION TESTS")
    print("=" * 60)
    print(f"API URL: {API_URL}")

    try:
        # Check API is running
        response = requests.get(f"{API_URL}/health", timeout=2)
        if response.status_code != 200:
            print("\n✗ API server is not running!")
            print("  Start with: uvicorn api.main:app --port 8000")
            return
    except requests.exceptions.ConnectionError:
        print("\n✗ Cannot connect to API server!")
        print("  Start with: uvicorn api.main:app --port 8000")
        return

    print("✓ API server is running")

    try:
        # Run tests
        email = test_user_registration()
        token, session_id = test_login(email)
        profile = test_get_user_profile(token)
        sessions = test_get_sessions(token)
        tfa_status = test_2fa_status(token)
        test_logout(token, session_id)
        test_openapi_docs()

        # Summary
        print_section("TEST SUMMARY")
        print("✓ All 7 tests passed!")
        print("\nYou can now test the frontend:")
        print("  1. Open browser: http://localhost:3000/login.html")
        print("  2. Login with:")
        print(f"     Email: {email}")
        print(f"     Password: TestPassword123")
        print("\nAPI Documentation:")
        print("  Swagger UI: http://localhost:8000/docs")
        print("  ReDoc: http://localhost:8000/redoc")

    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")

if __name__ == "__main__":
    main()
