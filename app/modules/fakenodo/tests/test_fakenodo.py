import io
import re


def test_create_deposition_returns_conceptrecid(test_client):
    payload = {"metadata": {"title": "Test deposition"}}
    resp = test_client.post("/deposit/depositions", json=payload)
    assert resp.status_code == 201
    data = resp.get_json()
    assert "conceptrecid" in data
    assert data["conceptrecid"] == data["id"]


def test_upload_file_and_get_deposition(test_client):
    # create
    resp = test_client.post("/deposit/depositions", json={"metadata": {"title": "Upload test"}})
    assert resp.status_code == 201
    dep = resp.get_json()
    dep_id = dep["id"]

    # upload file
    data = {"file": (io.BytesIO(b"hello world"), "test.csv")}
    upload_resp = test_client.post(
        f"/deposit/depositions/{dep_id}/files",
        data=data,
        content_type="multipart/form-data",
    )
    assert upload_resp.status_code == 201
    up = upload_resp.get_json()
    assert "files" in up
    assert up["files"][0]["filename"] == "test.csv"

    # get deposition and check files
    get_resp = test_client.get(f"/deposit/depositions/{dep_id}")
    assert get_resp.status_code == 200
    got = get_resp.get_json()
    assert any(f.get("filename") == "test.csv" for f in got.get("files", []))


def test_publish_creates_doi_and_versioning(test_client):
    # create
    resp = test_client.post("/deposit/depositions", json={"metadata": {"title": "Publish test"}})
    dep = resp.get_json()
    dep_id = dep["id"]

    # publish first time
    pub1 = test_client.post(f"/deposit/depositions/{dep_id}/actions/publish")
    assert pub1.status_code == 202
    data1 = pub1.get_json()
    assert "doi" in data1
    doi1 = data1["doi"]
    assert re.match(r"10\.5072/fakenodo\.\d+\.v1", doi1)

    # publish second time -> version increases
    pub2 = test_client.post(f"/deposit/depositions/{dep_id}/actions/publish")
    assert pub2.status_code == 202
    data2 = pub2.get_json()
    doi2 = data2["doi"]
    assert doi2 != doi1
    assert re.match(r"10\.5072/fakenodo\.\d+\.v2", doi2)

    # get deposition returns latest doi
    get_resp = test_client.get(f"/deposit/depositions/{dep_id}")
    got = get_resp.get_json()
    assert got.get("doi") == doi2
