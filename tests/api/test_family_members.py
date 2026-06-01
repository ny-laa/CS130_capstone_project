#tests for /api/users/{user_id}/family-members
#same shape as tests/api/test_users_messages.py -- TestClient +
#dependency_overrides for get_db + patch the service functions.

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from database import get_db
from main import app


def _override_db():
    yield MagicMock()


def _fake_member(user_id, name="Sarah", relation="Spouse"):
    m = MagicMock()
    m.id = uuid4()
    m.user_id = user_id
    m.name = name
    m.relation = relation
    m.created_at = datetime.now(timezone.utc)
    return m


def test_list_family_members():
    user_id = uuid4()
    rows = [_fake_member(user_id, "Sarah", "Spouse"), _fake_member(user_id, "Mark", "Son")]

    app.dependency_overrides[get_db] = _override_db
    with patch("api.family_members.list_family_members", return_value=rows):
        client = TestClient(app)
        r = client.get(f"/api/users/{user_id}/family-members")
    app.dependency_overrides.clear()

    assert r.status_code == 200
    body = r.json()
    assert len(body) == 2
    assert body[0]["name"] == "Sarah"
    assert body[0]["relation"] == "Spouse"
    assert body[1]["name"] == "Mark"


def test_create_family_member_201():
    user_id = uuid4()
    created = _fake_member(user_id, "Emma", "Daughter")

    app.dependency_overrides[get_db] = _override_db
    with patch("api.family_members.create_family_member", return_value=created) as mock_create:
        client = TestClient(app)
        r = client.post(
            f"/api/users/{user_id}/family-members",
            json={"name": "Emma", "relation": "Daughter"},
        )
    app.dependency_overrides.clear()

    assert r.status_code == 201
    assert r.json()["name"] == "Emma"
    assert mock_create.call_args.kwargs["name"] == "Emma"
    assert mock_create.call_args.kwargs["relation"] == "Daughter"


def test_create_family_member_404_when_user_missing():
    user_id = uuid4()

    app.dependency_overrides[get_db] = _override_db
    with patch(
        "api.family_members.create_family_member",
        side_effect=ValueError("User not found"),
    ):
        client = TestClient(app)
        r = client.post(
            f"/api/users/{user_id}/family-members", json={"name": "Ghost"}
        )
    app.dependency_overrides.clear()

    assert r.status_code == 404
    assert r.json()["detail"] == "User not found"


def test_create_family_member_400_on_bad_input():
    user_id = uuid4()

    app.dependency_overrides[get_db] = _override_db
    with patch(
        "api.family_members.create_family_member",
        side_effect=ValueError("Family member name cannot be empty"),
    ):
        client = TestClient(app)
        #pydantic min_length=1 catches "" before we hit the service, so we
        #send a name and rely on the service raising for some other reason.
        r = client.post(
            f"/api/users/{user_id}/family-members", json={"name": "ok"}
        )
    app.dependency_overrides.clear()

    assert r.status_code == 400


def test_create_family_member_422_on_pydantic_validation():
    #empty string violates min_length=1 -- fastapi/pydantic returns 422.
    user_id = uuid4()

    app.dependency_overrides[get_db] = _override_db
    with patch("api.family_members.create_family_member") as mock_create:
        client = TestClient(app)
        r = client.post(
            f"/api/users/{user_id}/family-members", json={"name": ""}
        )
    app.dependency_overrides.clear()

    assert r.status_code == 422
    mock_create.assert_not_called()


def test_get_family_member_404_when_missing():
    user_id, member_id = uuid4(), uuid4()

    app.dependency_overrides[get_db] = _override_db
    with patch("api.family_members.get_family_member", return_value=None):
        client = TestClient(app)
        r = client.get(f"/api/users/{user_id}/family-members/{member_id}")
    app.dependency_overrides.clear()

    assert r.status_code == 404


def test_patch_family_member():
    user_id, member_id = uuid4(), uuid4()
    updated = _fake_member(user_id, "Sarah J.", "Wife")

    app.dependency_overrides[get_db] = _override_db
    with patch("api.family_members.update_family_member", return_value=updated):
        client = TestClient(app)
        r = client.patch(
            f"/api/users/{user_id}/family-members/{member_id}",
            json={"relation": "Wife"},
        )
    app.dependency_overrides.clear()

    assert r.status_code == 200
    assert r.json()["relation"] == "Wife"


def test_delete_family_member_204():
    user_id, member_id = uuid4(), uuid4()

    app.dependency_overrides[get_db] = _override_db
    with patch("api.family_members.delete_family_member", return_value=True):
        client = TestClient(app)
        r = client.delete(f"/api/users/{user_id}/family-members/{member_id}")
    app.dependency_overrides.clear()

    assert r.status_code == 204


def test_delete_family_member_404_when_missing():
    user_id, member_id = uuid4(), uuid4()

    app.dependency_overrides[get_db] = _override_db
    with patch("api.family_members.delete_family_member", return_value=False):
        client = TestClient(app)
        r = client.delete(f"/api/users/{user_id}/family-members/{member_id}")
    app.dependency_overrides.clear()

    assert r.status_code == 404
