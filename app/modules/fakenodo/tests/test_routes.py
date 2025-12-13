"""
HTTP Tests for Fakenodo API endpoints.

These tests verify that all Fakenodo endpoints work correctly and follow
Zenodo API compatibility patterns.
"""

import json
from io import BytesIO


class TestCreateDeposition:
    """Tests for POST /deposit/depositions"""

    def test_create_deposition_with_metadata(self, test_client):
        """Create a deposition with metadata"""
        response = test_client.post(
            "/fakenodo/deposit/depositions",
            json={"metadata": {"title": "Test Dataset"}},
            content_type="application/json",
        )
        assert response.status_code == 201
        data = json.loads(response.data)
        assert "id" in data
        assert data["metadata"]["title"] == "Test Dataset"
        assert data["state"] == "draft"
        assert "conceptrecid" in data

    def test_create_deposition_without_metadata(self, test_client):
        """Create a deposition with empty metadata"""
        response = test_client.post("/fakenodo/deposit/depositions", json={}, content_type="application/json")
        assert response.status_code == 201
        data = json.loads(response.data)
        assert "id" in data
        assert data["metadata"] == {}

    def test_create_deposition_response_has_zenodo_fields(self, test_client):
        """Verify response includes Zenodo-compatible fields"""
        response = test_client.post(
            "/fakenodo/deposit/depositions", json={"metadata": {"title": "Test"}}, content_type="application/json"
        )
        data = json.loads(response.data)

        # Check Zenodo-compatible fields
        assert "id" in data
        assert "conceptrecid" in data
        assert "state" in data
        assert "links" in data
        assert "created_at" in data
        assert "updated_at" in data


class TestGetDeposition:
    """Tests for GET /deposit/depositions/<id>"""

    def test_get_existing_deposition(self, test_client):
        """Get an existing deposition"""
        # Create first
        create_resp = test_client.post(
            "/fakenodo/deposit/depositions", json={"metadata": {"title": "Test"}}, content_type="application/json"
        )
        dep_id = json.loads(create_resp.data)["id"]

        # Get it
        response = test_client.get(f"/fakenodo/deposit/depositions/{dep_id}")
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["id"] == dep_id

    def test_get_nonexistent_deposition(self, test_client):
        """Get a deposition that doesn't exist"""
        response = test_client.get("/fakenodo/deposit/depositions/99999")
        assert response.status_code == 404
        data = json.loads(response.data)
        assert "message" in data

    def test_list_all_depositions(self, test_client):
        """List all depositions"""
        # Create a couple
        test_client.post(
            "/fakenodo/deposit/depositions", json={"metadata": {"title": "Test 1"}}, content_type="application/json"
        )
        test_client.post(
            "/fakenodo/deposit/depositions", json={"metadata": {"title": "Test 2"}}, content_type="application/json"
        )

        response = test_client.get("/fakenodo/deposit/depositions")
        assert response.status_code == 200
        data = json.loads(response.data)
        assert "depositions" in data
        assert len(data["depositions"]) >= 2


class TestUpdateDeposition:
    """Tests for PUT /deposit/depositions/<id>"""

    def test_update_nonexistent_deposition(self, test_client):
        """Update a deposition that doesn't exist"""
        response = test_client.put(
            "/fakenodo/deposit/depositions/99999",
            json={"metadata": {"title": "Updated"}},
            content_type="application/json",
        )
        assert response.status_code == 404


class TestDeleteDeposition:
    """Tests for DELETE /deposit/depositions/<id>"""

    def test_delete_existing_deposition(self, test_client):
        """Delete an existing deposition"""
        # Create
        create_resp = test_client.post(
            "/fakenodo/deposit/depositions", json={"metadata": {"title": "ToDelete"}}, content_type="application/json"
        )
        dep_id = json.loads(create_resp.data)["id"]

        # Delete
        response = test_client.delete(f"/fakenodo/deposit/depositions/{dep_id}")
        assert response.status_code == 200
        data = json.loads(response.data)
        assert "message" in data

        # Verify it's gone
        get_resp = test_client.get(f"/fakenodo/deposit/depositions/{dep_id}")
        assert get_resp.status_code == 404

    def test_delete_nonexistent_deposition(self, test_client):
        """Delete a deposition that doesn't exist"""
        response = test_client.delete("/fakenodo/deposit/depositions/99999")
        assert response.status_code == 404


class TestUploadFile:
    """Tests for POST /deposit/depositions/<id>/files"""

    def test_upload_file_to_existing_deposition(self, test_client):
        """Upload a file to an existing deposition"""
        # Create deposition
        create_resp = test_client.post(
            "/fakenodo/deposit/depositions", json={"metadata": {"title": "Test"}}, content_type="application/json"
        )
        dep_id = json.loads(create_resp.data)["id"]

        # Upload file
        response = test_client.post(
            f"/fakenodo/deposit/depositions/{dep_id}/files",
            data={"file": (BytesIO(b"test content"), "test.txt")},
            content_type="multipart/form-data",
        )
        assert response.status_code == 201
        data = json.loads(response.data)
        assert "name" in data
        assert data["name"] == "test.txt"

    def test_upload_file_without_filename(self, test_client):
        """Upload a file without providing a name"""
        create_resp = test_client.post(
            "/fakenodo/deposit/depositions", json={"metadata": {"title": "Test"}}, content_type="application/json"
        )
        dep_id = json.loads(create_resp.data)["id"]

        response = test_client.post(
            f"/fakenodo/deposit/depositions/{dep_id}/files",
            data={"file": (BytesIO(b"test content"),)},
            content_type="multipart/form-data",
        )
        assert response.status_code == 400

    def test_upload_to_nonexistent_deposition(self, test_client):
        """Upload a file to a deposition that doesn't exist"""
        response = test_client.post(
            "/fakenodo/deposit/depositions/99999/files",
            data={"file": (BytesIO(b"test content"), "test.txt")},
            content_type="multipart/form-data",
        )
        assert response.status_code == 404


class TestErrorHandling:
    """Tests for consistent error handling"""

    def test_error_messages_are_consistent(self, test_client):
        """All error responses should use consistent format"""
        # Try various not-found scenarios
        # NOTE: Removed 'publish' and 'versions' endpoint from list as they are removed
        endpoints = [
            "/fakenodo/deposit/depositions/99999",
            "/fakenodo/deposit/depositions/99999/files",
        ]

        for endpoint in endpoints:
            # GET
            response = test_client.get(endpoint)
            if response.status_code == 404:
                data = json.loads(response.data)
                assert "message" in data, f"404 response missing 'message' field for {endpoint}"

            # DELETE
            if "depositions" in endpoint and endpoint.count("/") == 4:
                response = test_client.delete(endpoint)
                if response.status_code == 404:
                    data = json.loads(response.data)
                    assert "message" in data


class TestEndToEnd:
    """End-to-end tests for complete workflows"""

    def test_create_and_upload_workflow(self, test_client):
        """Test workflow: create -> upload (Publish step removed as endpoint is deprecated)"""
        # 1. Create deposition
        create_resp = test_client.post(
            "/fakenodo/deposit/depositions",
            json={"metadata": {"title": "Complete Test Dataset"}},
            content_type="application/json",
        )
        assert create_resp.status_code == 201
        dep_id = json.loads(create_resp.data)["id"]

        # 2. Upload files
        for i in range(2):
            upload_resp = test_client.post(
                f"/fakenodo/deposit/depositions/{dep_id}/files",
                data={"file": (BytesIO(f"content {i}".encode()), f"file{i}.txt")},
                content_type="multipart/form-data",
            )
            assert upload_resp.status_code == 201
