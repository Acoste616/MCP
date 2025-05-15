# Mark all tests in this file as async
pytestmark = pytest.mark.asyncio


async def test_register_new_user(client: AsyncClient, dbsession: AsyncSession):
    """Test user registration successfully creates a new user."""
    response = await client.post(
        f"{settings.API_V1_STR}/auth/register",
        json={
            "email": "newuser@example.com",
            "name": "New User",
            "password": "newpassword123",
            "role": "user", # Optional, defaults to "user"
            "is_active": True # Optional, defaults to True
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "newuser@example.com"
    assert data["name"] == "New User"
    assert "id" in data
    assert "created_at" in data

    # Verify user in database
    result = await dbsession.execute(select(User).where(User.email == "newuser@example.com"))
    db_user = result.scalar_one_or_none()
    assert db_user is not None
    assert db_user.email == "newuser@example.com"
    assert verify_password("newpassword123", db_user.hashed_password)


async def test_register_existing_user_email(client: AsyncClient, test_user: User):
    """Test registration fails if email already exists."""
    response = await client.post(
        f"{settings.API_V1_STR}/auth/register",
        json={
            "email": test_user.email, # Existing email
            "name": "Another User",
            "password": "password123",
        },
    )
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]

async def test_register_password_too_short(client: AsyncClient):
    """Test registration fails if password is too short."""
    response = await client.post(
        f"{settings.API_V1_STR}/auth/register",
        json={
            "email": "shortpass@example.com",
            "name": "Short Password User",
            "password": "123", # Too short
        },
    )
    assert response.status_code == 422 # Unprocessable Entity for validation errors
    data = response.json()
    assert "detail" in data
    found_password_error = False
    # Pydantic validation errors are in a list under "detail"
    for error in data.get("detail", []):
        if isinstance(error, dict) and error.get("loc") and "password" in error.get("loc"): # type: ignore
            # Example msg: "String should have at least 6 characters"
            assert "at least 6 characters" in error.get("msg", "").lower()
            found_password_error = True
            break
    assert found_password_error, "Password length validation error not found in response."

async def test_login_correct_credentials(client: AsyncClient, test_user: User):
    """Test login with correct credentials returns an access token."""
    response = await client.post(
        f"{settings.API_V1_STR}/auth/login",
        data={"username": test_user.email, "password": "testpassword"},
    )
    assert response.status_code == 200
    token_data = response.json()
    assert "access_token" in token_data
    assert token_data["token_type"] == "bearer"

async def test_login_incorrect_password(client: AsyncClient, test_user: User):
    """Test login with incorrect password fails."""
    response = await client.post(
        f"{settings.API_V1_STR}/auth/login",
        data={"username": test_user.email, "password": "wrongpassword"},
    )
    assert response.status_code == 401
    assert "Incorrect email or password" in response.json()["detail"]


async def test_login_nonexistent_user(client: AsyncClient):
    """Test login with a non-existent user email fails."""
    response = await client.post(
        f"{settings.API_V1_STR}/auth/login",
        data={"username": "nosuchuser@example.com", "password": "password"},
    )
    assert response.status_code == 401
    assert "Incorrect email or password" in response.json()["detail"]

async def test_login_inactive_user(client: AsyncClient, dbsession: AsyncSession):
    """Test login with an inactive user fails."""
    inactive_user = User(
        email="inactive@example.com",
        name="Inactive User",
        hashed_password="somepassword", # Hashed form of 'testpassword'
        is_active=False,
        role="user"
    )
    from app.core.security import get_password_hash # Local import if not at top
    inactive_user.hashed_password = get_password_hash("testpassword")
    dbsession.add(inactive_user)
    await dbsession.commit()

    response = await client.post(
        f"{settings.API_V1_STR}/auth/login",
        data={"username": inactive_user.email, "password": "testpassword"},
    )
    assert response.status_code == 400 # As per current auth.py logic
    assert "Inactive user" in response.json()["detail"]


async def test_logout_user(client: AsyncClient, test_user_auth_headers: dict):
    """Test logout endpoint."""
    response = await client.post(
        f"{settings.API_V1_STR}/auth/logout",
        headers=test_user_auth_headers, # Logout might require auth
    )
    assert response.status_code == 200
    assert "Successfully logged out" in response.json()["message"] 