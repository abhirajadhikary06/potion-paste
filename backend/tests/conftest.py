import pytest
from app import create_app, db
from app.models import User

@pytest.fixture
def app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def user(app):
    u = User(public_id="test-user-id", email="test@example.com", username="tester")
    u.set_password("SecurePass1")
    db.session.add(u)
    db.session.commit()
    return u
