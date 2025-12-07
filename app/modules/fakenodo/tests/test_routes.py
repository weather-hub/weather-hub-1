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

    def test_update_metadata_without_marking_dirty(self, test_client):
        """Updating metadata alone should NOT create new DOI"""
        # Create and publish
        create_resp = test_client.post(
            "/fakenodo/deposit/depositions", json={"metadata": {"title": "Original"}}, content_type="application/json"
        )
        dep_id = json.loads(create_resp.data)["id"]

        # Publish to get first DOI
        pub_resp = test_client.post(f"/fakenodo/deposit/depositions/{dep_id}/actions/publish")
        assert pub_resp.status_code == 202
        doi1 = json.loads(pub_resp.data)["doi"]

        # Update metadata
        update_resp = test_client.put(
            f"/fakenodo/deposit/depositions/{dep_id}",
            json={"metadata": {"title": "Updated"}},
            content_type="application/json",
        )
        assert update_resp.status_code == 200

        # Publish again - should be same DOI
        pub_resp2 = test_client.post(f"/fakenodo/deposit/depositions/{dep_id}/actions/publish")
        assert pub_resp2.status_code == 202
        doi2 = json.loads(pub_resp2.data)["doi"]
        assert doi1 == doi2, "DOI should not change when only metadata is updated"

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

    def test_upload_file_marks_dirty(self, test_client):
        """Uploading a file should create new DOI on next publish"""
        # Create and publish
        create_resp = test_client.post(
            "/fakenodo/deposit/depositions", json={"metadata": {"title": "Test"}}, content_type="application/json"
        )
        dep_id = json.loads(create_resp.data)["id"]

        pub_resp1 = test_client.post(f"/fakenodo/deposit/depositions/{dep_id}/actions/publish")
        doi1 = json.loads(pub_resp1.data)["doi"]

        # Upload file
        test_client.post(
            f"/fakenodo/deposit/depositions/{dep_id}/files",
            data={"file": (BytesIO(b"test content"), "test.txt")},
            content_type="multipart/form-data",
        )

        # Publish again - should get new DOI
        pub_resp2 = test_client.post(f"/fakenodo/deposit/depositions/{dep_id}/actions/publish")
        doi2 = json.loads(pub_resp2.data)["doi"]
        assert doi1 != doi2, "DOI should change when files are added"

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


class TestPublishDeposition:
    """Tests for POST /deposit/depositions/<id>/actions/publish"""

    def test_publish_creates_doi(self, test_client):
        """Publishing a deposition should create a DOI"""
        create_resp = test_client.post(
            "/fakenodo/deposit/depositions", json={"metadata": {"title": "Test"}}, content_type="application/json"
        )
        dep_id = json.loads(create_resp.data)["id"]

        response = test_client.post(f"/fakenodo/deposit/depositions/{dep_id}/actions/publish")
        assert response.status_code == 202
        data = json.loads(response.data)
        assert "doi" in data
        assert "version" in data

    def test_publish_increments_version(self, test_client):
        """Publishing twice after file change should increment version"""
        create_resp = test_client.post(
            "/fakenodo/deposit/depositions", json={"metadata": {"title": "Test"}}, content_type="application/json"
        )
        dep_id = json.loads(create_resp.data)["id"]

        # First publish
        pub_resp1 = test_client.post(f"/fakenodo/deposit/depositions/{dep_id}/actions/publish")
        v1_data = json.loads(pub_resp1.data)
        assert v1_data["version"] == 1

        # Upload file
        test_client.post(
            f"/fakenodo/deposit/depositions/{dep_id}/files",
            data={"file": (BytesIO(b"content"), "test.txt")},
            content_type="multipart/form-data",
        )

        # Second publish
        pub_resp2 = test_client.post(f"/fakenodo/deposit/depositions/{dep_id}/actions/publish")
        v2_data = json.loads(pub_resp2.data)
        assert v2_data["version"] == 2

    def test_publish_nonexistent_deposition(self, test_client):
        """Publish a deposition that doesn't exist"""
        response = test_client.post("/fakenodo/deposit/depositions/99999/actions/publish")
        assert response.status_code == 404


class TestListVersions:
    """Tests for GET /deposit/depositions/<id>/versions"""

    def test_list_versions(self, test_client):
        """List all versions for a deposition"""
        # Create and publish multiple times
        create_resp = test_client.post(
            "/fakenodo/deposit/depositions", json={"metadata": {"title": "Test"}}, content_type="application/json"
        )
        dep_id = json.loads(create_resp.data)["id"]

        # First publish
        test_client.post(f"/fakenodo/deposit/depositions/{dep_id}/actions/publish")

        # Add file and publish again
        test_client.post(
            f"/fakenodo/deposit/depositions/{dep_id}/files",
            data={"file": (BytesIO(b"content"), "test.txt")},
            content_type="multipart/form-data",
        )
        test_client.post(f"/fakenodo/deposit/depositions/{dep_id}/actions/publish")

        # List versions
        response = test_client.get(f"/fakenodo/deposit/depositions/{dep_id}/versions")
        assert response.status_code == 200
        data = json.loads(response.data)
        assert "versions" in data
        assert len(data["versions"]) == 2

    def test_list_versions_nonexistent(self, test_client):
        """List versions for a deposition that doesn't exist"""
        response = test_client.get("/fakenodo/deposit/depositions/99999/versions")
        assert response.status_code == 404


class TestErrorHandling:
    """Tests for consistent error handling"""

    def test_error_messages_are_consistent(self, test_client):
        """All error responses should use consistent format"""
        # Try various not-found scenarios
        endpoints = [
            "/fakenodo/deposit/depositions/99999",
            "/fakenodo/deposit/depositions/99999/files",
            "/fakenodo/deposit/depositions/99999/versions",
            "/fakenodo/deposit/depositions/99999/actions/publish",
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

    def test_complete_publication_workflow(self, test_client):
        """Test complete workflow: create -> upload -> publish"""
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

        # 3. Publish
        pub_resp = test_client.post(f"/fakenodo/deposit/depositions/{dep_id}/actions/publish")
        assert pub_resp.status_code == 202
        pub_data = json.loads(pub_resp.data)
        assert "doi" in pub_data
        assert pub_data["version"] == 1

        # 4. Verify state is published
        get_resp = test_client.get(f"/fakenodo/deposit/depositions/{dep_id}")
        assert get_resp.status_code == 200
        dep_data = json.loads(get_resp.data)
        assert dep_data["state"] == "published"

    def test_metadata_edit_then_file_upload_workflow(self, test_client):
        """Test workflow: create -> edit metadata -> publish -> add file -> republish"""
        # 1. Create
        create_resp = test_client.post(
            "/fakenodo/deposit/depositions",
            json={"metadata": {"title": "Original Title"}},
            content_type="application/json",
        )
        dep_id = json.loads(create_resp.data)["id"]

        # 2. Edit metadata
        test_client.put(
            f"/fakenodo/deposit/depositions/{dep_id}",
            json={"metadata": {"title": "Updated Title"}},
            content_type="application/json",
        )

        # 3. Publish v1
        pub1_resp = test_client.post(f"/fakenodo/deposit/depositions/{dep_id}/actions/publish")
        doi1 = json.loads(pub1_resp.data)["doi"]

        # 4. Add file
        test_client.post(
            f"/fakenodo/deposit/depositions/{dep_id}/files",
            data={"file": (BytesIO(b"content"), "data.txt")},
            content_type="multipart/form-data",
        )

        # 5. Publish v2
        pub2_resp = test_client.post(f"/fakenodo/deposit/depositions/{dep_id}/actions/publish")
        doi2 = json.loads(pub2_resp.data)["doi"]

        # Verify DOI changed only after file upload
        assert doi1 != doi2
        assert "v1" in doi1
        assert "v2" in doi2
