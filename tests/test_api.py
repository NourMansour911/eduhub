from pathlib import Path
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel
from unittest.mock import AsyncMock, MagicMock

from core import get_settings
from routers.home_router import home_route
from routers.lecture_router import lecture_route
from routers.assistant_router import assistant_route
from routers.grading_router import grading_route
from routers.vectordb_router import vectordb_route
from orchestrators import get_lecture_orchestrator
from services.lectures import lecture_service
from services.summarize import get_summarize_service
from services.grading import get_set_reference_service, get_set_score_service
from services.vdb_service import get_vdb_service


ROOT_DIR = Path(__file__).resolve().parents[1]

TEST_SUBJECT_ID = "test_subject"
TEST_LECTURE_ID = "test_lecture"
TEST_COLLECTION_NAME = "test_collection"
TEST_USER_ID = "test_user"
TEST_SESSION_ID = "test_session"


class HomeResponseSchema(BaseModel):
    app_name: str
    version: str
    status: str
    timestamp: str


class _DummySettings:
    APP_NAME = "test_eduhub"
    APP_VERSION = "test_0.0.0"


@pytest.fixture
def mock_lecture_orchestrator():
    """Create a mock LectureOrchestrator."""
    mock = AsyncMock()
    mock.store_lecture_with_summaries = AsyncMock(
        return_value={
            "lecture_id": TEST_LECTURE_ID,
            "subject_id": TEST_SUBJECT_ID,
            "status": "success",
        }
    )
    return mock


@pytest.fixture
def mock_lecture_service():
    """Create a mock LectureService."""
    mock = AsyncMock()
    mock.get_lecture = AsyncMock(
        return_value={
            "lecture_id": TEST_LECTURE_ID,
            "subject_id": TEST_SUBJECT_ID,
            "title": "Test Lecture",
        }
    )
    mock.get_lectures_by_subject = AsyncMock(
        return_value={
            "subject_id": TEST_SUBJECT_ID,
            "lectures": [],
            "count": 0,
        }
    )
    mock.delete_lecture = AsyncMock(
        return_value={
            "deleted_count": 1,
            "status": "success",
        }
    )
    mock.delete_lectures_by_subject = AsyncMock(
        return_value={
            "deleted_count": 0,
            "status": "success",
        }
    )
    return mock


@pytest.fixture
def mock_summarize_service():
    """Create a mock SummarizeService."""
    mock = AsyncMock()
    mock.get_summary = AsyncMock(return_value="This is a test summary.")
    return mock


@pytest.fixture
def mock_set_reference_service():
    """Create a mock SetReferenceService."""
    mock = AsyncMock()
    mock.store_reference = AsyncMock(
        return_value={
            "status": "success",
            "message": "Reference answer stored",
        }
    )
    return mock


@pytest.fixture
def mock_set_score_service():
    """Create a mock SetScoreService."""
    mock = AsyncMock()
    mock.batch_grade = AsyncMock(
        return_value={
            "status": "success",
            "graded_count": 0,
            "grades": [],
        }
    )
    return mock


@pytest.fixture
def mock_vdb_service():
    """Create a mock VDBService."""
    mock = MagicMock()
    mock.get_collection_info = MagicMock(
        return_value={
            "collection_name": TEST_COLLECTION_NAME,
            "vector_size": 768,
            "chunk_count": 0,
        }
    )
    mock.get_chunks = MagicMock(
        return_value={
            "collection_name": TEST_COLLECTION_NAME,
            "page": 1,
            "limit": 10,
            "total_chunks": 0,
            "chunks": [],
        }
    )
    mock.delete_collection = MagicMock(
        return_value={
            "collection_name": TEST_COLLECTION_NAME,
            "status": "deleted",
        }
    )
    return mock


@pytest.fixture
def client(
    mock_lecture_orchestrator,
    mock_lecture_service,
    mock_summarize_service,
    mock_set_reference_service,
    mock_set_score_service,
    mock_vdb_service,
) -> TestClient:
    """Create a test client with mocked dependencies."""
    app = FastAPI()
    app.include_router(home_route)
    app.include_router(lecture_route)
    app.include_router(assistant_route)
    app.include_router(grading_route)
    app.include_router(vectordb_route)

    app.dependency_overrides[get_settings] = lambda: _DummySettings()
    app.dependency_overrides[get_lecture_orchestrator] = lambda: mock_lecture_orchestrator
    app.dependency_overrides[lecture_service.get_lecture_service] = lambda: mock_lecture_service
    app.dependency_overrides[get_summarize_service] = lambda: mock_summarize_service
    app.dependency_overrides[get_set_reference_service] = lambda: mock_set_reference_service
    app.dependency_overrides[get_set_score_service] = lambda: mock_set_score_service
    app.dependency_overrides[get_vdb_service] = lambda: mock_vdb_service

    return TestClient(app)


class TestHealthEndpoints:
    """Test suite for health check endpoints."""

    def test_root_endpoint_returns_200(self, client):
        """Test that root endpoint returns 200 status."""
        response = client.get("/")
        assert response.status_code == 200

    def test_root_endpoint_response_schema(self, client):
        """Test that root endpoint returns correct schema."""
        response = client.get("/")
        data = HomeResponseSchema.model_validate(response.json())
        
        assert data.app_name == "test_eduhub"
        assert data.version == "test_0.0.0"
        assert data.status == "running"
        assert data.timestamp

    def test_root_endpoint_response_structure(self, client):
        """Test that response contains all required fields."""
        response = client.get("/")
        data = response.json()
        
        required_fields = {"app_name", "version", "status", "timestamp"}
        assert required_fields.issubset(set(data.keys())), "Missing required fields in response"


class TestLectureEndpoints:
    """Test suite for lecture management endpoints."""

    def test_post_store_lecture_returns_200(self, client):
        """Test that store lecture endpoint returns 200 status."""
        payload = {
            "subject_id": TEST_SUBJECT_ID,
            "lecture_content": {"content": "test content"},
        }
        response = client.post("/lectures", json=payload)
        assert response.status_code == 200

    def test_post_store_lecture_response_has_required_fields(self, client):
        """Test that store lecture response has required fields."""
        payload = {
            "subject_id": TEST_SUBJECT_ID,
            "lecture_content": {"content": "test content"},
        }
        response = client.post("/lectures", json=payload)
        data = response.json()
        
        assert "lecture_id" in data
        assert "subject_id" in data
        assert data["subject_id"] == TEST_SUBJECT_ID

    def test_get_lecture_by_id_returns_200(self, client):
        """Test that get lecture by ID endpoint returns 200 status."""
        response = client.get(f"/lectures/{TEST_LECTURE_ID}")
        assert response.status_code == 200

    def test_get_lecture_by_id_returns_lecture_data(self, client):
        """Test that get lecture endpoint returns lecture data."""
        response = client.get(f"/lectures/{TEST_LECTURE_ID}")
        data = response.json()
        
        assert data["lecture_id"] == TEST_LECTURE_ID
        assert data["subject_id"] == TEST_SUBJECT_ID

    def test_get_lectures_by_subject_returns_200(self, client):
        """Test that get lectures by subject endpoint returns 200 status."""
        response = client.get(f"/lectures/subject/{TEST_SUBJECT_ID}")
        assert response.status_code == 200

    def test_get_lectures_by_subject_returns_list(self, client):
        """Test that get lectures by subject returns a list."""
        response = client.get(f"/lectures/subject/{TEST_SUBJECT_ID}")
        data = response.json()
        
        assert "subject_id" in data
        assert "lectures" in data
        assert isinstance(data["lectures"], list)

    def test_delete_lecture_by_id_returns_200(self, client):
        """Test that delete lecture endpoint returns 200 status."""
        response = client.delete(f"/lectures/{TEST_LECTURE_ID}")
        assert response.status_code == 200

    def test_delete_lecture_by_id_returns_deletion_status(self, client):
        """Test that delete lecture returns deletion status."""
        response = client.delete(f"/lectures/{TEST_LECTURE_ID}")
        data = response.json()
        
        assert "deleted_count" in data
        assert "status" in data

    def test_delete_lectures_by_subject_returns_200(self, client):
        """Test that delete lectures by subject endpoint returns 200 status."""
        response = client.delete(f"/lectures/subject/{TEST_SUBJECT_ID}")
        assert response.status_code == 200

    def test_delete_lectures_by_subject_returns_deletion_status(self, client):
        """Test that delete lectures by subject returns deletion status."""
        response = client.delete(f"/lectures/subject/{TEST_SUBJECT_ID}")
        data = response.json()
        
        assert "deleted_count" in data
        assert "status" in data


class TestAssistantEndpoints:
    """Test suite for assistant/AI endpoints."""

    def test_post_summarize_returns_200(self, client):
        """Test that summarize endpoint returns 200 status."""
        payload = {
            "lecture_id": TEST_LECTURE_ID,
            "length": 0,
        }
        response = client.post("/assistant/summarize", json=payload)
        assert response.status_code == 200

    def test_post_summarize_returns_summary(self, client):
        """Test that summarize endpoint returns summary text."""
        payload = {
            "lecture_id": TEST_LECTURE_ID,
            "length": 0,
        }
        response = client.post("/assistant/summarize", json=payload)
        data = response.json()
        
        assert "summary" in data
        assert isinstance(data["summary"], str)

    def test_post_chat_returns_200(self, client):
        """Test that chat endpoint returns 200 status."""
        payload = {"message": "What is in this lecture?"}
        response = client.post(
            f"/assistant/chat/{TEST_USER_ID}/{TEST_SESSION_ID}",
            json=payload
        )
        assert response.status_code == 200

    def test_post_chat_returns_response(self, client):
        """Test that chat endpoint returns AI response."""
        payload = {"message": "What is in this lecture?"}
        response = client.post(
            f"/assistant/chat/{TEST_USER_ID}/{TEST_SESSION_ID}",
            json=payload
        )
        data = response.json()
        
        assert "ai_response" in data


class TestGradingEndpoints:
    """Test suite for essay grading endpoints."""

    def test_post_set_reference_returns_200(self, client):
        """Test that set reference endpoint returns 200 status."""
        payload = {
            "essay_id": "essay_1",
            "reference_answer": "This is a reference answer",
        }
        response = client.post("/essay/set-reference", json=payload)
        assert response.status_code == 200

    def test_post_set_reference_returns_status(self, client):
        """Test that set reference endpoint returns success status."""
        payload = {
            "essay_id": "essay_1",
            "reference_answer": "This is a reference answer",
        }
        response = client.post("/essay/set-reference", json=payload)
        data = response.json()
        
        assert "status" in data
        assert data["status"] == "success"

    def test_post_grade_batch_returns_200(self, client):
        """Test that grade batch endpoint returns 200 status."""
        payload = {
            "essays": [
                {
                    "essay_id": "essay_1",
                    "student_answer": "Student answer text",
                }
            ]
        }
        response = client.post("/essay/grade-batch", json=payload)
        assert response.status_code == 200

    def test_post_grade_batch_returns_grades(self, client):
        """Test that grade batch endpoint returns grades."""
        payload = {
            "essays": [
                {
                    "essay_id": "essay_1",
                    "student_answer": "Student answer text",
                }
            ]
        }
        response = client.post("/essay/grade-batch", json=payload)
        data = response.json()
        
        assert "status" in data
        assert "graded_count" in data
        assert "grades" in data


class TestVectorDBEndpoints:
    """Test suite for vector database endpoints."""

    def test_get_collection_info_returns_200(self, client):
        """Test that get collection info endpoint returns 200 status."""
        response = client.get(f"/vdb/{TEST_COLLECTION_NAME}/info")
        assert response.status_code == 200

    def test_get_collection_info_returns_metadata(self, client):
        """Test that get collection info returns collection metadata."""
        response = client.get(f"/vdb/{TEST_COLLECTION_NAME}/info")
        data = response.json()
        
        assert "collection_name" in data
        assert data["collection_name"] == TEST_COLLECTION_NAME

    def test_get_collection_chunks_returns_200(self, client):
        """Test that get chunks endpoint returns 200 status."""
        response = client.get(f"/vdb/{TEST_COLLECTION_NAME}/chunks?page=1&limit=10")
        assert response.status_code == 200

    def test_get_collection_chunks_returns_paginated_chunks(self, client):
        """Test that get chunks endpoint returns paginated chunks."""
        response = client.get(f"/vdb/{TEST_COLLECTION_NAME}/chunks?page=1&limit=10")
        data = response.json()
        
        assert "collection_name" in data
        assert "chunks" in data
        assert isinstance(data["chunks"], list)
        assert "page" in data
        assert "limit" in data

    def test_delete_collection_returns_200(self, client):
        """Test that delete collection endpoint returns 200 status."""
        response = client.delete(f"/vdb/{TEST_COLLECTION_NAME}")
        assert response.status_code == 200

    def test_delete_collection_returns_status(self, client):
        """Test that delete collection endpoint returns deletion status."""
        response = client.delete(f"/vdb/{TEST_COLLECTION_NAME}")
        data = response.json()
        
        assert "collection_name" in data
        assert "status" in data