"""Tests for FastAPI dashboard endpoints."""

import sys
import tempfile
from pathlib import Path

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cerebro.dashboard import app, get_db
from cerebro.db import create_tables, get_bookmark, upsert_bookmark
from cerebro.models import Bookmark


@pytest.fixture
def db_session():
    """Provide a fresh file-based database session for each test."""
    # Use temp file to ensure single shared database across threads
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    db_url = f"sqlite:///{db_path}"
    engine = sa.create_engine(db_url, future=True)
    create_tables(engine)

    from sqlalchemy.orm import sessionmaker

    factory = sessionmaker(bind=engine)
    session = factory()

    yield session

    session.close()
    engine.dispose()
    Path(db_path).unlink(missing_ok=True)


@pytest.fixture
def test_client(db_session: Session):
    """Provide a test client with the same database session."""

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def _sample_bookmark(**overrides):
    """Create a sample bookmark for testing."""
    defaults = {
        "id": "test-bm-1",
        "url": "https://example.com/test",
        "title": "Test Bookmark",
        "domain": "example.com",
        "tags": ["test", "python"],
        "description": "A test bookmark for testing",
    }
    defaults.update(overrides)
    return Bookmark(**defaults)


def test_list_bookmarks_empty(db_session, test_client):
    """Test that empty database returns 200 with empty state."""
    response = test_client.get("/bookmarks")
    assert response.status_code == 200
    assert "No bookmarks found" in response.text


def test_list_bookmarks_with_data(db_session, test_client):
    """Test that bookmarks list page shows seeded bookmark."""
    bm = _sample_bookmark()
    upsert_bookmark(db_session, bm)

    response = test_client.get("/bookmarks")
    assert response.status_code == 200
    assert "Test Bookmark" in response.text


def test_search_endpoint(db_session, test_client):
    """Test search endpoint returns matching bookmark."""
    bm = _sample_bookmark(title="Python Tutorial", description="Learn python")
    upsert_bookmark(db_session, bm)

    response = test_client.get("/search?q=python")
    assert response.status_code == 200
    assert "Python Tutorial" in response.text


def test_search_empty_query(db_session, test_client):
    """Test search with empty query returns empty state."""
    response = test_client.get("/search?q=")
    assert response.status_code == 200
    assert "No bookmarks found" in response.text


def test_bookmark_detail_not_found(db_session, test_client):
    """Test that missing bookmark returns 404."""
    response = test_client.get("/bookmark/nonexistent-id")
    assert response.status_code == 404


def test_bookmark_detail_found(db_session, test_client):
    """Test that existing bookmark returns detail page."""
    bm = _sample_bookmark(id="detail-1", title="Detail Test")
    upsert_bookmark(db_session, bm)

    response = test_client.get("/bookmark/detail-1")
    assert response.status_code == 200
    assert "Detail Test" in response.text


def test_stats_page(db_session, test_client):
    """Test that stats page shows bookmark counts."""
    bm1 = _sample_bookmark(id="stats-1", is_dead_link=False)
    bm2 = _sample_bookmark(id="stats-2", is_dead_link=True, http_status=404)
    upsert_bookmark(db_session, bm1)
    upsert_bookmark(db_session, bm2)

    response = test_client.get("/stats")
    assert response.status_code == 200
    assert "Total Bookmarks" in response.text
    assert "Dead Links" in response.text


def test_api_ingest_creates_bookmark(db_session, test_client):
    """Test that POST /api/ingest creates bookmark and returns 201."""
    response = test_client.post(
        "/api/ingest",
        params={
            "url": "https://example.com/new",
            "title": "New Bookmark",
            "tags": ["new", "test"],
            "description": "Created via API",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert data["status"] == "created"


def test_root_redirects_to_bookmarks(db_session, test_client):
    """Test that root path redirects to /bookmarks."""
    response = test_client.get("/", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/bookmarks"


def test_edit_bookmark_form_renders(db_session, test_client):
    """Test GET /bookmark/{id}/edit returns the edit form."""
    bm = _sample_bookmark(id="edit-1", title="Edit Me")
    upsert_bookmark(db_session, bm)

    response = test_client.get("/bookmark/edit-1/edit")
    assert response.status_code == 200
    assert "Edit Bookmark" in response.text
    assert "Edit Me" in response.text


def test_edit_bookmark_updates_fields(db_session, test_client):
    """Test POST /bookmark/{id}/edit updates title, tags, and description."""
    bm = _sample_bookmark(id="edit-2", title="Old Title", tags=["old"], description="old desc")
    upsert_bookmark(db_session, bm)

    response = test_client.post(
        "/bookmark/edit-2/edit",
        params={"title": "New Title", "tags": "new, shiny", "description": "new desc"},
    )
    assert response.status_code == 200

    updated = get_bookmark(db_session, "edit-2")
    assert updated is not None
    assert updated.title == "New Title"
    assert updated.tags == ["new", "shiny"]
    assert updated.description == "new desc"


def test_edit_bookmark_not_found(db_session, test_client):
    """Test editing a missing bookmark returns 404."""
    response = test_client.get("/bookmark/missing-id/edit")
    assert response.status_code == 404


def test_delete_bookmark_redirects(db_session, test_client):
    """Test DELETE /bookmark/{id} removes bookmark and redirects."""
    bm = _sample_bookmark(id="delete-1", title="Delete Me")
    upsert_bookmark(db_session, bm)

    response = test_client.delete("/bookmark/delete-1", headers={"HX-Request": "true"})
    assert response.status_code == 200
    assert response.headers["HX-Redirect"] == "/bookmarks"

    assert get_bookmark(db_session, "delete-1") is None


def test_delete_bookmark_not_found(db_session, test_client):
    """Test deleting a missing bookmark returns 404."""
    response = test_client.delete("/bookmark/missing-id", headers={"HX-Request": "true"})
    assert response.status_code == 404


def test_bulk_tags_updates_multiple(db_session, test_client):
    """Test POST /bookmarks/bulk-tags appends tags to selected bookmarks."""
    bm1 = _sample_bookmark(id="bulk-1", title="Bulk 1", tags=["python"])
    bm2 = _sample_bookmark(id="bulk-2", title="Bulk 2", tags=["rust"])
    upsert_bookmark(db_session, bm1)
    upsert_bookmark(db_session, bm2)

    response = test_client.post(
        "/bookmarks/bulk-tags",
        data={"ids": ["bulk-1", "bulk-2"], "tags": "shared, important"},
    )
    assert response.status_code == 200

    assert get_bookmark(db_session, "bulk-1").tags == ["python", "shared", "important"]
    assert get_bookmark(db_session, "bulk-2").tags == ["rust", "shared", "important"]


def test_dead_link_filter(db_session, test_client):
    """Test /bookmarks?dead_only=1 filters dead links."""
    live = _sample_bookmark(id="live-1", title="Live", is_dead_link=False)
    dead = _sample_bookmark(id="dead-1", title="Dead", is_dead_link=True, http_status=404)
    upsert_bookmark(db_session, live)
    upsert_bookmark(db_session, dead)

    response = test_client.get("/bookmarks?dead_only=1")
    assert response.status_code == 200
    assert "Dead" in response.text
    assert "Live" not in response.text
