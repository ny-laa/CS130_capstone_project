#tests for /api/users/{user_id}/contacts including the ?q= name search.

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from database import get_db
from main import app


def _override_db():
    yield MagicMock()


def _fake_contact(user_id, name="Mrs. Carter"):
    c = MagicMock()
    c.id = uuid4()
    c.user_id = user_id
    c.name = name
    c.role = "Office Manager"
    c.org = "Mark's School"
    c.phone = "(310) 555-0201"
    c.created_at = datetime.now(timezone.utc)
    return c


def test_list_contacts_no_query_calls_list():
    user_id = uuid4()
    rows = [_fake_contact(user_id)]

    app.dependency_overrides[get_db] = _override_db
    with patch("api.contacts.list_contacts", return_value=rows) as mock_list, \
         patch("api.contacts.find_contacts_by_name") as mock_find:
        client = TestClient(app)
        r = client.get(f"/api/users/{user_id}/contacts")
    app.dependency_overrides.clear()

    assert r.status_code == 200
    assert r.json()[0]["name"] == "Mrs. Carter"
    mock_list.assert_called_once()
    mock_find.assert_not_called()


def test_list_contacts_with_q_calls_search():
    user_id = uuid4()
    rows = [_fake_contact(user_id)]

    app.dependency_overrides[get_db] = _override_db
    with patch("api.contacts.list_contacts") as mock_list, \
         patch("api.contacts.find_contacts_by_name", return_value=rows) as mock_find:
        client = TestClient(app)
        r = client.get(f"/api/users/{user_id}/contacts?q=carter")
    app.dependency_overrides.clear()

    assert r.status_code == 200
    mock_list.assert_not_called()
    assert mock_find.call_args.args[2] == "carter"


def test_create_contact_201():
    user_id = uuid4()
    created = _fake_contact(user_id)

    app.dependency_overrides[get_db] = _override_db
    with patch("api.contacts.create_contact", return_value=created) as mock_create:
        client = TestClient(app)
        r = client.post(
            f"/api/users/{user_id}/contacts",
            json={
                "name": "Mrs. Carter",
                "role": "Office Manager",
                "org": "Mark's School",
                "phone": "(310) 555-0201",
            },
        )
    app.dependency_overrides.clear()

    assert r.status_code == 201
    body = r.json()
    assert body["name"] == "Mrs. Carter"
    assert body["phone"] == "(310) 555-0201"
    kwargs = mock_create.call_args.kwargs
    assert kwargs["role"] == "Office Manager"
    assert kwargs["org"] == "Mark's School"


def test_create_contact_404_when_user_missing():
    user_id = uuid4()

    app.dependency_overrides[get_db] = _override_db
    with patch(
        "api.contacts.create_contact",
        side_effect=ValueError("User not found"),
    ):
        client = TestClient(app)
        r = client.post(f"/api/users/{user_id}/contacts", json={"name": "X"})
    app.dependency_overrides.clear()

    assert r.status_code == 404


def test_patch_contact():
    user_id, contact_id = uuid4(), uuid4()
    updated = _fake_contact(user_id)
    updated.phone = "(310) 555-9999"

    app.dependency_overrides[get_db] = _override_db
    with patch("api.contacts.update_contact", return_value=updated):
        client = TestClient(app)
        r = client.patch(
            f"/api/users/{user_id}/contacts/{contact_id}",
            json={"phone": "(310) 555-9999"},
        )
    app.dependency_overrides.clear()

    assert r.status_code == 200
    assert r.json()["phone"] == "(310) 555-9999"


def test_patch_contact_404():
    user_id, contact_id = uuid4(), uuid4()

    app.dependency_overrides[get_db] = _override_db
    with patch(
        "api.contacts.update_contact",
        side_effect=ValueError("Contact not found"),
    ):
        client = TestClient(app)
        r = client.patch(
            f"/api/users/{user_id}/contacts/{contact_id}", json={"name": "x"}
        )
    app.dependency_overrides.clear()

    assert r.status_code == 404


def test_delete_contact_204():
    user_id, contact_id = uuid4(), uuid4()

    app.dependency_overrides[get_db] = _override_db
    with patch("api.contacts.delete_contact", return_value=True):
        client = TestClient(app)
        r = client.delete(f"/api/users/{user_id}/contacts/{contact_id}")
    app.dependency_overrides.clear()

    assert r.status_code == 204


def test_delete_contact_404():
    user_id, contact_id = uuid4(), uuid4()

    app.dependency_overrides[get_db] = _override_db
    with patch("api.contacts.delete_contact", return_value=False):
        client = TestClient(app)
        r = client.delete(f"/api/users/{user_id}/contacts/{contact_id}")
    app.dependency_overrides.clear()

    assert r.status_code == 404
