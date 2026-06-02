#tests for /api/users/{user_id}/providers including the ?specialty= filter
#that the orchestrator uses when picking the user's default dentist / plumber.

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from database import get_db
from main import app


def _override_db():
    yield MagicMock()


def _fake_provider(user_id, name="Dr. Lee", specialty="Dentist"):
    p = MagicMock()
    p.id = uuid4()
    p.user_id = user_id
    p.name = name
    p.specialty = specialty
    p.practice = "UCLA Westside Dental"
    p.created_at = datetime.now(timezone.utc)
    return p


def test_list_providers_no_filter():
    user_id = uuid4()
    rows = [_fake_provider(user_id)]

    app.dependency_overrides[get_db] = _override_db
    with patch("api.providers.list_providers", return_value=rows) as mock_list, \
         patch("api.providers.find_providers_by_specialty") as mock_find:
        client = TestClient(app)
        r = client.get(f"/api/users/{user_id}/providers")
    app.dependency_overrides.clear()

    assert r.status_code == 200
    assert r.json()[0]["name"] == "Dr. Lee"
    mock_list.assert_called_once()
    mock_find.assert_not_called()


def test_list_providers_with_specialty_calls_search():
    user_id = uuid4()
    rows = [_fake_provider(user_id)]

    app.dependency_overrides[get_db] = _override_db
    with patch("api.providers.list_providers") as mock_list, \
         patch("api.providers.find_providers_by_specialty", return_value=rows) as mock_find:
        client = TestClient(app)
        r = client.get(f"/api/users/{user_id}/providers?specialty=Dentist")
    app.dependency_overrides.clear()

    assert r.status_code == 200
    mock_list.assert_not_called()
    assert mock_find.call_args.args[2] == "Dentist"


def test_create_provider_201():
    user_id = uuid4()
    created = _fake_provider(user_id)

    app.dependency_overrides[get_db] = _override_db
    with patch("api.providers.create_provider", return_value=created) as mock_create:
        client = TestClient(app)
        r = client.post(
            f"/api/users/{user_id}/providers",
            json={
                "name": "Dr. Lee",
                "specialty": "Dentist",
                "practice": "UCLA Westside Dental",
            },
        )
    app.dependency_overrides.clear()

    assert r.status_code == 201
    body = r.json()
    assert body["name"] == "Dr. Lee"
    assert body["specialty"] == "Dentist"
    kwargs = mock_create.call_args.kwargs
    assert kwargs["practice"] == "UCLA Westside Dental"


def test_create_provider_404_when_user_missing():
    user_id = uuid4()

    app.dependency_overrides[get_db] = _override_db
    with patch(
        "api.providers.create_provider",
        side_effect=ValueError("User not found"),
    ):
        client = TestClient(app)
        r = client.post(f"/api/users/{user_id}/providers", json={"name": "X"})
    app.dependency_overrides.clear()

    assert r.status_code == 404


def test_patch_provider():
    user_id, provider_id = uuid4(), uuid4()
    updated = _fake_provider(user_id, specialty="Orthodontist")

    app.dependency_overrides[get_db] = _override_db
    with patch("api.providers.update_provider", return_value=updated):
        client = TestClient(app)
        r = client.patch(
            f"/api/users/{user_id}/providers/{provider_id}",
            json={"specialty": "Orthodontist"},
        )
    app.dependency_overrides.clear()

    assert r.status_code == 200
    assert r.json()["specialty"] == "Orthodontist"


def test_delete_provider_204():
    user_id, provider_id = uuid4(), uuid4()

    app.dependency_overrides[get_db] = _override_db
    with patch("api.providers.delete_provider", return_value=True):
        client = TestClient(app)
        r = client.delete(f"/api/users/{user_id}/providers/{provider_id}")
    app.dependency_overrides.clear()

    assert r.status_code == 204


def test_delete_provider_404():
    user_id, provider_id = uuid4(), uuid4()

    app.dependency_overrides[get_db] = _override_db
    with patch("api.providers.delete_provider", return_value=False):
        client = TestClient(app)
        r = client.delete(f"/api/users/{user_id}/providers/{provider_id}")
    app.dependency_overrides.clear()

    assert r.status_code == 404
