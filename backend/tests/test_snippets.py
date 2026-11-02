def test_create_snippet_requires_auth(client):
    res = client.post("/api/snippets", json={"title": "Hi", "code": "print(1)"})
    assert res.status_code == 401

def test_create_and_list(client, user):
    # Login first
    client.post("/api/auth/login", json={"email": "test@example.com", "password": "SecurePass1"})
    res = client.post("/api/snippets", json={
        "title": "Hello",
        "code": "print('hi')",
        "language": "python",
        "is_private": True,
    })
    assert res.status_code == 201
    sn = res.get_json()["snippet"]
    assert sn["title"] == "Hello"
    assert sn["language"] == "python"

    res = client.get("/api/snippets")
    assert res.status_code == 200
    assert res.get_json()["total"] >= 1
