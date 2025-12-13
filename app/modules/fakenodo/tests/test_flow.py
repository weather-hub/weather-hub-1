from app.modules.dataset.routes import FakenodoAdapter
from app.modules.fakenodo.services import FakenodoService


def test_metadata_edit_does_not_create_new_doi(test_client, tmp_path):
    """Test that editing metadata alone doesn't create a new DOI"""
    wd = str(tmp_path)
    service = FakenodoService(working_dir=wd)

    # create and publish -> first DOI
    rec = service.create_deposition(metadata={"title": "original"})
    dep_id = rec["id"]
    ver1 = service.publish_deposition(dep_id, False)
    assert ver1 is not None and "doi" in ver1
    doi1 = ver1["doi"]

    # edit metadata only
    updated = service.update_metadata(dep_id, {"title": "changed"})
    assert updated is not None

    # publish again -> DOI should be the same (no new version)
    ver2 = service.publish_deposition(dep_id, False)
    assert ver2 is not None
    assert ver2["doi"] == doi1


def test_upload_creates_new_doi(test_client, tmp_path):
    """Test that uploading a file creates a new DOI on next publish"""
    wd = str(tmp_path)
    service = FakenodoService(working_dir=wd)

    rec = service.create_deposition(metadata={"title": "original"})
    dep_id = rec["id"]
    ver1 = service.publish_deposition(dep_id)
    doi1 = ver1["doi"]

    # upload a file (marks dirty)
    file_rec = service.upload_file(dep_id, "file.txt", b"hello world")
    assert file_rec is not None

    # publish again -> new DOI
    ver2 = service.publish_deposition(dep_id)
    assert ver2 is not None
    doi2 = ver2["doi"]
    assert doi2 != doi1


def test_adapter_dataset_flow(test_client, tmp_path):
    """Test the FakenodoAdapter workflow with dataset objects"""
    wd = str(tmp_path)
    adapter = FakenodoAdapter(working_dir=wd)

    class DummyDataset:
        def __init__(self, id, title=None):
            self.id = id
            self.title = title

    class DummyFeatureModel:
        def __init__(self, filename, path):
            self.filename = filename
            self.file_path = path

    # Use a unique ID to avoid conflicts with other tests
    import time

    unique_id = int(time.time() * 1000) % 1000000
    ds = DummyDataset(unique_id, title="mydataset")

    # create deposition via adapter
    resp = adapter.create_new_deposition(ds)
    assert resp.get("id") is not None
    dep_id = resp.get("id")

    # create a temp file to upload
    p = tmp_path / "fm.txt"
    p.write_text("content")
    fm = DummyFeatureModel("fm.txt", str(p))

    upload_rec = adapter.upload_file(ds, dep_id, fm)
    assert upload_rec is not None

    ver = adapter.publish_deposition(dep_id)
    assert ver is not None and "doi" in ver

    doi = adapter.get_doi(dep_id)
    assert doi == ver.get("doi")
