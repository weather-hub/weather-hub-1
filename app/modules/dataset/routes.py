import json
import logging
import os
import shutil
import tempfile
import uuid
from datetime import datetime, timezone
from typing import Optional
from zipfile import ZipFile

from flask import (
    abort,
    current_app,
    jsonify,
    make_response,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)
from flask_login import current_user, login_required

from app.modules.community.repositories import CommunityRepository
from app.modules.dataset import dataset_bp
from app.modules.dataset.forms import DataSetForm, DatasetCommentForm
from app.modules.dataset.models import DSDownloadRecord
from app.modules.dataset.services import (
    AuthorService,
    DatasetCommentService,
    DataSetService,
    DOIMappingService,
    DSDownloadRecordService,
    DSMetaDataEditLogService,
    DSMetaDataService,
    DSViewRecordService,
)
from app.modules.fakenodo.services import FakenodoService
from app.modules.follow.services import FollowService
from app.modules.zenodo.services import ZenodoService

follow_service = FollowService()

logger = logging.getLogger(__name__)


dataset_service = DataSetService()
author_service = AuthorService()
dsmetadata_service = DSMetaDataService()


class FakenodoAdapter:
    """Adapter that exposes create_new_deposition, upload_file, publish_deposition
    and get_doi so the rest of the code doesn't need to change.

    Uses dataset.id to generate stable DOIs even if fakenodo_db.json is reset.
    """

    def __init__(self, working_dir: str | None = None):
        self.service = FakenodoService(working_dir=working_dir)
        self.dataset_id = None  # Store dataset ID for DOI generation

    def create_new_deposition(self, dataset) -> dict:
        # Store dataset.id to use for stable DOI generation
        self.dataset_id = getattr(dataset, "id", None)
        metadata = {
            "title": getattr(dataset, "title", f"dataset-{self.dataset_id}"),
        }
        # Pasar dataset.id como deposition_id para DOI consistente desde v1
        rec = self.service.create_deposition(metadata=metadata, deposition_id=self.dataset_id)
        return {"id": rec["id"], "conceptrecid": True, "metadata": rec.get("metadata", {})}

    def upload_file(self, dataset, deposition_id, feature_model) -> Optional[dict]:

        name = getattr(feature_model, "filename", None) or getattr(feature_model, "name", None)
        path = getattr(feature_model, "file_path", None) or getattr(feature_model, "path", None)
        content = None
        try:
            if path and os.path.exists(path):
                with open(path, "rb") as fh:
                    content = fh.read()
        except Exception:
            content = None

        if not name:
            name = f"feature_model_{getattr(feature_model, 'id', uuid.uuid4())}.bin"

        return self.service.upload_file(deposition_id, name, content)

    def publish_deposition(self, deposition_id):
        version = self.service.publish_deposition(deposition_id)
        if version and self.dataset_id:
            # This ensures stable DOIs even if fakenodo_db.json is reset
            new_doi = f"10.1234/fakenodo.{self.dataset_id}.v{version.get('version', 1)}"
            version["doi"] = new_doi
        return version

    def get_doi(self, deposition_id):
        rec = self.service.get_deposition(deposition_id)
        if not rec:
            return None

        if self.dataset_id and rec.get("versions"):
            # Get the version number from the last version
            version_num = rec["versions"][-1].get("version", 1)
            return f"10.1234/fakenodo.{self.dataset_id}.v{version_num}"

        # Fallback to stored DOI
        doi = rec.get("doi")
        if doi:
            return doi
        versions = rec.get("versions") or []
        if versions:
            return versions[-1].get("doi")
        return None


def get_zenodo_client(working_dir: str | None = None):
    """Return a zenodo-like client depending on environment configuration.

    If the environment variable `FAKENODO_URL` or `USE_FAKE_ZENODO` is set the
    function returns a `FakenodoAdapter`, otherwise it returns the real
    `ZenodoService`.
    """
    # Prefer explicit environment opt-in for the fake service
    if os.getenv("FAKENODO_URL") or os.getenv("USE_FAKE_ZENODO"):
        return FakenodoAdapter(working_dir=working_dir)

    # Otherwise try real Zenodo and fall back to the fake service if the
    # connection fails (e.g. SSL verification issues in some environments).
    try:
        zs = ZenodoService()
        try:
            if zs.test_connection():
                return zs
        except Exception:
            # test_connection failed (network/ssl); fall through to fake
            logger = logging.getLogger(__name__)
            logger.warning("ZenodoService test_connection failed, falling back to FakenodoAdapter")
            return FakenodoAdapter(working_dir=working_dir)
    except Exception:
        # constructing ZenodoService failed for any reason -> fallback
        logger = logging.getLogger(__name__)
        logger.warning("Unable to initialize ZenodoService, using FakenodoAdapter")
        return FakenodoAdapter(working_dir=working_dir)


zenodo_service = get_zenodo_client()
doi_mapping_service = DOIMappingService()
ds_view_record_service = DSViewRecordService()


@dataset_bp.route("/dataset/upload", methods=["GET", "POST"])
@login_required
def create_dataset():
    form = DataSetForm()
    if request.method == "POST":
        dataset = None

        # Debug: log raw form data
        logger.info(f"Raw request data - publication_type: {request.form.get('publication_type')}")
        logger.info(
            f"All feature_models publication_type values: {request.form.getlist('feature_models-0-publication_type')}"
        )

        # Check available choices
        logger.info(f"Available publication_type choices: {form.publication_type.choices}")
        if form.feature_models and len(form.feature_models) > 0:
            logger.info(f"Feature model 0 publication_type choices: {form.feature_models[0].publication_type.choices}")

        if not form.validate_on_submit():
            logger.error(f"Form validation failed: {form.errors}")
            return jsonify({"message": form.errors}), 400

        try:
            logger.info("Creating dataset...")
            dataset = dataset_service.create_from_form(form=form, current_user=current_user)
            logger.info(f"Created dataset: {dataset}")
            dataset_service.move_feature_models(dataset)
        except ValueError as e:
            # Business / validation error (e.g. our validate_dataset_package raised ValueError)
            logger.info(f"Validation error while creating dataset: {e}")
            return jsonify({"message": str(e)}), 400

        except Exception:
            # Unexpected error: log full trace, return generic message to client
            logger.exception("Exception while creating dataset")
            # For security do not leak internal trace to client; return generic message.
            return jsonify({"message": "Internal server error while creating dataset"}), 500

        # send dataset as deposition to Zenodo
        data = {}
        try:
            zenodo_response_json = zenodo_service.create_new_deposition(dataset)
            response_data = json.dumps(zenodo_response_json)
            data = json.loads(response_data)
        except Exception as exc:
            data = {}
            zenodo_response_json = {}
            logger.exception(f"Exception while create dataset data in Zenodo {exc}")

        if data.get("conceptrecid"):
            deposition_id = data.get("id")

            # update dataset with deposition id in Zenodo
            dataset_service.update_dsmetadata(dataset.ds_meta_data_id, deposition_id=deposition_id)

            try:
                # iterate for each feature model (one feature model = one request to Zenodo)
                for feature_model in dataset.feature_models:
                    zenodo_service.upload_file(dataset, deposition_id, feature_model)

                # publish deposition
                zenodo_service.publish_deposition(deposition_id)

                # update DOI
                deposition_doi = zenodo_service.get_doi(deposition_id)
                dataset_service.update_dsmetadata(dataset.ds_meta_data_id, dataset_doi=deposition_doi)
            except Exception as e:
                msg = f"it has not been possible upload feature models in Zenodo and update the DOI: {e}"
                return jsonify({"message": msg}), 200

        try:
            follow_service.notify_dataset_published(dataset)
        except Exception:
            current_app.logger.exception("Error sending 'dataset published' notification")

        # Delete temp folder
        file_path = current_user.temp_folder()
        if os.path.exists(file_path) and os.path.isdir(file_path):
            shutil.rmtree(file_path)

        msg = "Everything works!"
        return jsonify({"message": msg}), 200

    return render_template("dataset/upload_dataset.html", form=form)


@dataset_bp.route("/dataset/list", methods=["GET", "POST"])
@login_required
def list_dataset():
    # load communities to allow proposing datasets to a community from the list view
    try:
        community_repo = CommunityRepository()
        communities = community_repo.session.query(community_repo.model).all()
    except Exception:
        communities = []

    return render_template(
        "dataset/list_datasets.html",
        datasets=dataset_service.get_synchronized(current_user.id),
        local_datasets=dataset_service.get_unsynchronized(current_user.id),
        communities=communities,
    )


@dataset_bp.route("/dataset/file/upload", methods=["POST"])
@login_required
def upload():
    logger.info(f"Upload request from user {current_user.id}")
    file = request.files.get("file")
    temp_folder = current_user.temp_folder()

    # Validate file exists and has valid extension (case-insensitive)
    if not file or not file.filename:
        logger.warning("No file provided in upload request")
        return jsonify({"message": "No file provided"}), 400

    logger.info(f"Received file: {file.filename}")
    filename_lower = file.filename.lower()
    valid_extensions = (".csv", ".txt", ".md")
    if not any(filename_lower.endswith(ext) for ext in valid_extensions):
        logger.warning(f"Invalid file extension: {file.filename}")
        return jsonify({"message": f"Invalid file type. Allowed: {', '.join(valid_extensions)}"}), 400
    # create temp folder
    if not os.path.exists(temp_folder):
        os.makedirs(temp_folder)

    file_path = os.path.join(temp_folder, file.filename)

    if os.path.exists(file_path):
        # Generate unique filename (by recursion)
        base_name, extension = os.path.splitext(file.filename)
        i = 1
        while os.path.exists(os.path.join(temp_folder, f"{base_name} ({i}){extension}")):
            i += 1
        new_filename = f"{base_name} ({i}){extension}"
        file_path = os.path.join(temp_folder, new_filename)
    else:
        new_filename = file.filename

    try:
        file.save(file_path)
        logger.info(f"File saved successfully: {file_path} ({os.path.getsize(file_path)} bytes)")
    except Exception as e:
        logger.error(f"Error saving file {file.filename}: {str(e)}")
        return jsonify({"message": str(e)}), 500

    return (
        jsonify(
            {
                "message": "File uploaded and validated successfully",
                "filename": new_filename,
            }
        ),
        200,
    )


@dataset_bp.route("/dataset/file/delete", methods=["POST"])
def delete():
    data = request.get_json()
    filename = data.get("file")
    temp_folder = current_user.temp_folder()
    filepath = os.path.join(temp_folder, filename)

    if os.path.exists(filepath):
        os.remove(filepath)
        return jsonify({"message": "File deleted successfully"})

    return jsonify({"error": "Error: File not found"})


@dataset_bp.route("/dataset/download/<int:dataset_id>", methods=["GET"])
def download_dataset(dataset_id):
    dataset = dataset_service.get_or_404(dataset_id)

    file_path = f"uploads/user_{dataset.user_id}/dataset_{dataset.id}/"

    temp_dir = tempfile.mkdtemp()
    zip_path = os.path.join(temp_dir, f"dataset_{dataset_id}.zip")

    with ZipFile(zip_path, "w") as zipf:
        for subdir, dirs, files in os.walk(file_path):
            for file in files:
                full_path = os.path.join(subdir, file)

                relative_path = os.path.relpath(full_path, file_path)

                zipf.write(
                    full_path,
                    arcname=os.path.join(os.path.basename(zip_path[:-4]), relative_path),
                )

    user_cookie = request.cookies.get("download_cookie")
    if not user_cookie:
        # Generate a new unique identifier if it does not exist
        user_cookie = str(uuid.uuid4())
        # Save the cookie to the user's browser
        resp = make_response(
            send_from_directory(
                temp_dir,
                f"dataset_{dataset_id}.zip",
                as_attachment=True,
                mimetype="application/zip",
            )
        )
        resp.set_cookie("download_cookie", user_cookie)
    else:
        resp = send_from_directory(
            temp_dir,
            f"dataset_{dataset_id}.zip",
            as_attachment=True,
            mimetype="application/zip",
        )

    # Check if the download record already exists for this cookie
    existing_record = DSDownloadRecord.query.filter_by(
        user_id=current_user.id if current_user.is_authenticated else None,
        dataset_id=dataset_id,
        download_cookie=user_cookie,
    ).first()

    if not existing_record:
        # Record the download in your database
        DSDownloadRecordService().create(
            user_id=current_user.id if current_user.is_authenticated else None,
            dataset_id=dataset_id,
            download_date=datetime.now(timezone.utc),
            download_cookie=user_cookie,
        )

    return resp


@dataset_bp.route("/doi/<path:doi>/", methods=["GET"])
def subdomain_index(doi):
    # Find dataset by DOI - each version is a separate dataset
    ds_meta_data = dsmetadata_service.filter_by_doi(doi)

    if not ds_meta_data:
        abort(404)

    # Get dataset
    dataset = ds_meta_data.data_set

    # Save the cookie to the user's browser
    user_cookie = ds_view_record_service.create_cookie(dataset=dataset)
    resp = make_response(render_template("dataset/view_dataset.html", dataset=dataset))
    resp.set_cookie("view_cookie", user_cookie)

    return resp


@dataset_bp.route("/dataset/unsynchronized/<int:dataset_id>/", methods=["GET"])
@login_required
def get_unsynchronized_dataset(dataset_id):
    # Get dataset
    dataset = dataset_service.get_unsynchronized_dataset(current_user.id, dataset_id)

    if not dataset:
        abort(404)

    return render_template("dataset/view_dataset.html", dataset=dataset)


edit_log_service = DSMetaDataEditLogService()


@dataset_bp.route("/dataset/<int:dataset_id>/edit", methods=["GET", "POST"])
@login_required
def edit_dataset(dataset_id):
    """Edit dataset metadata (minor edits that don't generate new version)."""
    dataset = dataset_service.get_or_404(dataset_id)

    # Check ownership
    if dataset.user_id != current_user.id:
        abort(403)

    if request.method == "GET":
        return render_template("dataset/edit_dataset.html", dataset=dataset)

    try:
        changes = []
        ds_meta = dataset.ds_meta_data

        new_title = request.form.get("title", "").strip()
        if new_title and new_title != ds_meta.title:
            changes.append({"field": "title", "old": ds_meta.title, "new": new_title})
            ds_meta.title = new_title

        new_description = request.form.get("description", "").strip()
        if new_description and new_description != ds_meta.description:
            changes.append(
                {
                    "field": "description",
                    "old": ds_meta.description[:100] + "..." if len(ds_meta.description) > 100 else ds_meta.description,
                    "new": new_description[:100] + "..." if len(new_description) > 100 else new_description,
                }
            )
            ds_meta.description = new_description

        new_tags = request.form.get("tags", "").strip()
        if new_tags != (ds_meta.tags or ""):
            changes.append({"field": "tags", "old": ds_meta.tags or "", "new": new_tags})
            ds_meta.tags = new_tags

        if changes:
            edit_log_service.log_multiple_edits(
                ds_meta_data_id=ds_meta.id,
                user_id=current_user.id,
                changes=changes,
            )

            if ds_meta.deposition_id:
                fakenodo_service = FakenodoService()
                fakenodo_service.update_metadata(
                    ds_meta.deposition_id,
                    {"title": ds_meta.title, "description": ds_meta.description, "tags": ds_meta.tags},
                )

            from app import db

            db.session.commit()

            return jsonify({"message": "Dataset updated successfully", "changes": len(changes)}), 200
        else:
            return jsonify({"message": "No changes detected"}), 200

    except Exception as e:
        logger.exception(f"Error updating dataset {dataset_id}: {e}")
        return jsonify({"message": f"Error updating dataset: {str(e)}"}), 500


@dataset_bp.route("/dataset/<int:dataset_id>/versions", methods=["GET"])
def view_dataset_versions(dataset_id):
    """View all published versions of a dataset."""
    dataset = dataset_service.get_or_404(dataset_id)
    ds_meta = dataset.ds_meta_data

    versions = []
    if ds_meta.deposition_id:
        fakenodo_service = FakenodoService()
        raw_versions = fakenodo_service.list_versions(ds_meta.deposition_id) or []

        for v in raw_versions:
            # v["files"] already contains the parsed list of files from to_dict()
            files_list = v.get("files", [])
            v["files_count"] = len(files_list)
            logger.info(f"Version {v.get('version')}: {len(files_list)} files - {[f['name'] for f in files_list]}")
            versions.append(v)

    return render_template(
        "dataset/versions.html",
        dataset=dataset,
        versions=versions,
    )


@dataset_bp.route("/dataset/<int:dataset_id>/changelog", methods=["GET"])
def view_dataset_changelog(dataset_id):
    """View changelog of minor edits."""
    dataset = dataset_service.get_or_404(dataset_id)
    edit_logs = edit_log_service.get_changelog_by_dataset_id(dataset_id)

    return render_template(
        "dataset/changelog.html",
        dataset=dataset,
        edit_logs=edit_logs,
    )


@dataset_bp.route("/api/dataset/<int:dataset_id>/changelog", methods=["GET"])
def api_dataset_changelog(dataset_id):
    """API endpoint for dataset changelog."""
    dataset = dataset_service.get_or_404(dataset_id)
    edit_logs = edit_log_service.get_changelog_by_dataset_id(dataset_id)

    return jsonify(
        {
            "dataset_id": dataset_id,
            "dataset_title": dataset.ds_meta_data.title,
            "changelog": [log.to_dict() for log in edit_logs],
        }
    )


@dataset_bp.route("/dataset/<int:dataset_id>/republish", methods=["GET"])
@login_required
def republish_dataset_form(dataset_id):
    """Show form to upload new files for re-publication."""
    dataset = dataset_service.get_or_404(dataset_id)

    if dataset.user_id != current_user.id:
        abort(403)

    # Check if dataset is published
    if not dataset.ds_meta_data.dataset_doi:
        return redirect(url_for("dataset.subdomain_index", doi=dataset.ds_meta_data.dataset_doi))

    return render_template("dataset/republish_dataset.html", dataset=dataset)


@dataset_bp.route("/dataset/<int:dataset_id>/republish", methods=["POST"])
@login_required
def republish_dataset(dataset_id):
    """
    Re-publish dataset with new/modified files.
    Generates new version with new DOI.
    """
    dataset = dataset_service.get_or_404(dataset_id)

    if dataset.user_id != current_user.id:
        logger.warning(
            f"User {current_user.id} ({current_user.email}) attempted to republish "
            f"dataset {dataset_id} owned by user {dataset.user_id}"
        )
        abort(403)

    temp_folder = current_user.temp_folder()
    logger.info(
        f"Republish request for dataset {dataset_id} by user {current_user.id} "
        f"({current_user.email}), temp folder: {temp_folder}"
    )

    if not os.path.exists(temp_folder):
        logger.warning(f"Temp folder does not exist: {temp_folder}")
        return (
            jsonify(
                {
                    "message": "No files uploaded yet. Please drag and drop files to the upload area "
                    "before clicking Republish."
                }
            ),
            400,
        )

    temp_files = os.listdir(temp_folder)
    if not temp_files:
        logger.warning(f"Temp folder is empty: {temp_folder}")
        return (
            jsonify(
                {
                    "message": "No files uploaded yet. Please drag and drop files to the upload area "
                    "before clicking Republish."
                }
            ),
            400,
        )

    logger.info(f"Found {len(temp_files)} files in temp folder: {temp_files}")

    try:
        ds_meta = dataset.ds_meta_data

        if not ds_meta.deposition_id:
            return jsonify({"message": "Dataset has no Fakenodo deposition"}), 400

        fakenodo_service = FakenodoService()

        # Upload each file from temp folder (marks dirty=True)
        uploaded_files = []
        temp_folder_files = os.listdir(temp_folder) if os.path.exists(temp_folder) else []
        logger.info(f"Files in temp folder {temp_folder}: {temp_folder_files}")

        for filename in temp_folder_files:
            file_path = os.path.join(temp_folder, filename)
            logger.info(f"Processing file: {filename}, path: {file_path}, is_file: {os.path.isfile(file_path)}")

            if os.path.isfile(file_path):
                with open(file_path, "rb") as f:
                    content = f.read()
                logger.info(f"File {filename} size: {len(content)} bytes")

                result = fakenodo_service.upload_file(ds_meta.deposition_id, filename, content)
                logger.info(f"Fakenodo upload result for {filename}: {result}")

                if result:
                    uploaded_files.append(filename)
                    logger.info(f"Uploaded file {filename} to deposition {ds_meta.deposition_id}")
                else:
                    logger.warning(f"Fakenodo upload returned None/False for {filename}")
            else:
                logger.warning(f"Skipping {filename} - not a file")

        if not uploaded_files:
            logger.error(f"No files uploaded. Temp folder: {temp_folder}, files found: {temp_folder_files}")
            return (
                jsonify({"message": "No valid files were uploaded. Please check that files are properly uploaded."}),
                400,
            )

        # Publish new version (dirty=True generates v2, v3, etc.)
        version = fakenodo_service.publish_deposition(ds_meta.deposition_id)

        if not version:
            return jsonify({"message": "Failed to publish new version"}), 500

        # Get new DOI
        new_doi = version.get("doi")
        old_doi = ds_meta.dataset_doi

        logger.info(f"Creating NEW dataset for version {version.get('version')}: {new_doi}")

        # Create a CLONE of the current dataset with the new DOI
        from app import db
        from app.modules.dataset.models import DataSet as DataSetModel
        from app.modules.dataset.models import DSMetaData, DSMetrics
        from app.modules.featuremodel.models import FeatureModel
        from app.modules.hubfile.models import Hubfile

        # Clone metrics (or create default if none exist)
        old_metrics = ds_meta.ds_metrics
        if old_metrics:
            new_metrics = DSMetrics(
                number_of_models=old_metrics.number_of_models, number_of_features=old_metrics.number_of_features
            )
        else:
            # Create default metrics if original dataset has none
            new_metrics = DSMetrics(number_of_models="0", number_of_features="0")
        db.session.add(new_metrics)
        db.session.flush()

        # Clone DSMetaData
        logger.info(f"Cloning DSMetaData - Original deposition_id: {ds_meta.deposition_id}")
        new_ds_meta = DSMetaData(
            deposition_id=ds_meta.deposition_id,  # MANTENER el mismo deposition_id
            title=ds_meta.title,
            description=ds_meta.description,
            publication_type=ds_meta.publication_type,
            publication_doi=ds_meta.publication_doi,
            dataset_doi=new_doi,  # NEW DOI
            tags=ds_meta.tags,
            ds_metrics_id=new_metrics.id,
        )
        db.session.add(new_ds_meta)
        db.session.flush()
        logger.info(
            f"New DSMetaData created - deposition_id: {new_ds_meta.deposition_id}, "
            f"dataset_doi: {new_ds_meta.dataset_doi}"
        )

        # Clone Dataset
        new_dataset = DataSetModel(
            user_id=dataset.user_id, ds_meta_data_id=new_ds_meta.id, created_at=datetime.now(timezone.utc)
        )
        db.session.add(new_dataset)
        db.session.flush()

        # Clone ALL existing FeatureModels and Hubfiles
        for fm in dataset.feature_models:
            new_fm = FeatureModel(data_set_id=new_dataset.id)
            db.session.add(new_fm)
            db.session.flush()

            # Clone all files from this feature model
            for file in fm.files:
                new_file = Hubfile(name=file.name, checksum=file.checksum, size=file.size, feature_model_id=new_fm.id)
                db.session.add(new_file)

                # Copy physical file
                import shutil as sh

                old_path = file.get_path()
                new_path = new_file.get_path()
                os.makedirs(os.path.dirname(new_path), exist_ok=True)
                if os.path.exists(old_path):
                    sh.copy2(old_path, new_path)
                    logger.info(f"Copied file: {old_path} -> {new_path}")

        db.session.flush()

        # Now add NEW files from temp to the new dataset
        # Get or create a FeatureModel for new files
        new_fm = FeatureModel.query.filter_by(data_set_id=new_dataset.id).first()
        if not new_fm:
            new_fm = FeatureModel(data_set_id=new_dataset.id)
            db.session.add(new_fm)
            db.session.flush()

        # Copy new files from temp folder
        import hashlib

        for filename in uploaded_files:
            temp_file_path = os.path.join(temp_folder, filename)

            # Read file content to calculate checksum
            with open(temp_file_path, "rb") as f:
                content = f.read()
                checksum = hashlib.md5(content, usedforsecurity=False).hexdigest()

            # Create Hubfile entry
            new_hubfile = Hubfile(name=filename, checksum=checksum, size=len(content), feature_model_id=new_fm.id)
            db.session.add(new_hubfile)
            db.session.flush()

            # Copy physical file to dataset folder
            dest_path = new_hubfile.get_path()
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            sh.copy2(temp_file_path, dest_path)
            logger.info(f"Added new file: {filename} -> {dest_path}")

        db.session.commit()

        # Clean temp folder
        if os.path.exists(temp_folder):
            shutil.rmtree(temp_folder)

        logger.info(
            f"Created NEW dataset {new_dataset.id} (cloned from {dataset_id}) "
            f"for version v{version.get('version')} with DOI: {new_doi}. "
            f"Added {len(uploaded_files)} new files."
        )

        return (
            jsonify(
                {
                    "message": "New version published successfully",
                    "version": version.get("version"),
                    "doi": new_doi,
                    "old_doi": old_doi,
                    "files_uploaded": len(uploaded_files),
                    "files": uploaded_files,
                }
            ),
            200,
        )

    except Exception as e:
        logger.exception(f"Error republishing dataset {dataset_id}: {e}")
        return jsonify({"message": f"Error: {str(e)}"}), 500


# ===================== DATASET COMMENTS ROUTES =====================


comment_service = DatasetCommentService()


@dataset_bp.route("/dataset/<int:dataset_id>/comments", methods=["GET"])
def get_dataset_comments(dataset_id):
    """Get all comments for a dataset."""
    try:
        comments = comment_service.get_comments_by_dataset(dataset_id)
        return jsonify({"comments": [comment.to_dict() for comment in comments]}), 200
    except Exception as e:
        logger.exception(f"Error getting comments for dataset {dataset_id}: {e}")
        return jsonify({"message": "Error retrieving comments"}), 500


@dataset_bp.route("/dataset/<int:dataset_id>/comments", methods=["POST"])
@login_required
def create_dataset_comment(dataset_id):
    """Create a new comment on a dataset."""
    try:
        # Verify dataset exists
        dataset = dataset_service.get_by_id(dataset_id)
        if not dataset:
            return jsonify({"message": "Dataset not found"}), 404

        # Get comment content from request
        data = request.get_json() if request.is_json else request.form
        content = data.get("content", "").strip()

        if not content:
            return jsonify({"message": "Comment content is required"}), 400

        # Create comment
        comment = comment_service.create_comment(
            dataset_id=dataset_id, user_id=current_user.id, content=content
        )

        return jsonify({"message": "Comment posted successfully", "comment": comment.to_dict()}), 201

    except ValueError as e:
        return jsonify({"message": str(e)}), 400
    except Exception as e:
        logger.exception(f"Error creating comment on dataset {dataset_id}: {e}")
        return jsonify({"message": "Error creating comment"}), 500


@dataset_bp.route("/dataset/comments/<int:comment_id>", methods=["PUT"])
@login_required
def update_dataset_comment(comment_id):
    """Update an existing comment."""
    try:
        data = request.get_json() if request.is_json else request.form
        content = data.get("content", "").strip()

        if not content:
            return jsonify({"message": "Comment content is required"}), 400

        comment = comment_service.update_comment(comment_id=comment_id, content=content, user_id=current_user.id)

        return jsonify({"message": "Comment updated successfully", "comment": comment.to_dict()}), 200

    except ValueError as e:
        return jsonify({"message": str(e)}), 400
    except Exception as e:
        logger.exception(f"Error updating comment {comment_id}: {e}")
        return jsonify({"message": "Error updating comment"}), 500


@dataset_bp.route("/dataset/comments/<int:comment_id>", methods=["DELETE"])
@login_required
def delete_dataset_comment(comment_id):
    """Delete a comment."""
    try:
        # Check if user is admin
        is_admin = hasattr(current_user, "is_admin") and current_user.is_admin

        comment_service.delete_comment(comment_id=comment_id, user_id=current_user.id, is_admin=is_admin)

        return jsonify({"message": "Comment deleted successfully"}), 200

    except ValueError as e:
        return jsonify({"message": str(e)}), 400
    except Exception as e:
        logger.exception(f"Error deleting comment {comment_id}: {e}")
        return jsonify({"message": "Error deleting comment"}), 500
