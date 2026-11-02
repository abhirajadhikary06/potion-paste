def test_register_and_login(client):
    res = client.post("/api/auth/register", json={
        "email": "new@example.com",
        "username": "newuser",
        "password": "SecurePass1",
    })
    assert res.status_code == 201
    data = res.get_json()
    assert data["user"]["username"] == "newuser"

    res = client.post("/api/auth/login", json={
        "email": "new@example.com",
        "password": "SecurePass1",
    })
    assert res.status_code == 200

def test_weak_password_rejected(client):
    res = client.post("/api/auth/register", json={
        "email": "a@b.com",
        "username": "abc",
        "password": "short",
    })
    assert res.status_code == 400
