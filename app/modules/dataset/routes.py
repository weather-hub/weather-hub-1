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

from app.modules.comments.forms import CommentForm
from app.modules.comments.models import Comment
from app.modules.comments.services import CommentService
from app.modules.community.repositories import CommunityRepository
from app.modules.dataset import dataset_bp
from app.modules.dataset.forms import DataSetForm, DataSetVersionForm
from app.modules.dataset.models import DSDownloadRecord
from app.modules.dataset.services import (
    AuthorService,
    DataSetConceptService,
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
dataset_concept_service = DataSetConceptService()
ds_metadata_edit_log_service = DSMetaDataEditLogService()


class FakenodoAdapter:
    def __init__(self, working_dir: str | None = None):
        self.service = FakenodoService(working_dir=working_dir)
        self.dataset_id = None

    def publish_new_version(self, form, original_dataset, current_user, is_major=False):
        from app.modules.dataset.services import DataSetService

        _dataset_service = DataSetService()
        new_dataset = _dataset_service.create_from_form(form=form, current_user=current_user, allow_empty_package=True)
        new_dataset.ds_concept_id = original_dataset.ds_concept_id
        new_dataset.is_latest = True
        try:
            from app import db

            db.session.add(new_dataset)
            db.session.flush()
            from app.modules.dataset.models import DataSet

            DataSet.query.filter(
                DataSet.ds_concept_id == original_dataset.ds_concept_id, DataSet.id != new_dataset.id
            ).update({DataSet.is_latest: False})
            db.session.commit()
        except Exception:
            logger.exception("Failed to update concept linkage or latest flags")

        _dataset_service.move_feature_models(new_dataset)
        data = self.create_new_deposition(new_dataset)
        deposition_id = data.get("id")

        for feature_model in new_dataset.feature_models:
            self.upload_file(new_dataset, deposition_id, feature_model)

        self.publish_deposition(deposition_id)
        new_doi = self.get_doi(deposition_id)
        doi_to_store = new_doi if is_major else original_dataset.ds_meta_data.dataset_doi
        _dataset_service.update_dsmetadata(
            new_dataset.ds_meta_data_id, deposition_id=deposition_id, dataset_doi=doi_to_store
        )
        return new_dataset

    def create_new_deposition(self, dataset) -> dict:
        self.dataset_id = getattr(dataset, "id", None)
        metadata = {
            "title": getattr(dataset, "title", f"dataset-{self.dataset_id}"),
        }
        rec = self.service.create_deposition(metadata=metadata)
        return {"id": rec["id"], "conceptrecid": rec.get("conceptrecid"), "metadata": rec.get("metadata", {})}

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
            new_doi = f"10.1234/fakenodo.{self.dataset_id}.v{version.get('version', 1)}"
            version["doi"] = new_doi
        return version

    def get_doi(self, deposition_id):
        rec = self.service.get_deposition(deposition_id)
        if not rec:
            return None
        if self.dataset_id and rec.get("versions"):
            version_num = rec["versions"][-1].get("version", 1)
            return f"10.1234/fakenodo.{self.dataset_id}.v{version_num}"
        doi = rec.get("doi")
        if doi:
            return doi
        versions = rec.get("versions") or []
        if versions:
            return versions[-1].get("doi")
        return None

    def get_concept_doi(self, deposition_id):
        rec = self.service.get_deposition(deposition_id)
        if not rec:
            return None
        cdoi = rec.get("conceptdoi")
        if cdoi:
            return cdoi
        versions = rec.get("versions") or []
        if versions:
            return versions[-1].get("conceptdoi")
        return None


def get_zenodo_client(working_dir: str | None = None):
    if os.getenv("FAKENODO_URL") or os.getenv("USE_FAKE_ZENODO"):
        return FakenodoAdapter(working_dir=working_dir)
    try:
        zs = ZenodoService()
        try:
            if zs.test_connection():
                return zs
            else:
                logger.warning("ZenodoService test_connection returned False, falling back to FakenodoAdapter")
                return FakenodoAdapter(working_dir=working_dir)
        except Exception:
            logger.warning("ZenodoService test_connection failed with error, falling back to FakenodoAdapter")
            return FakenodoAdapter(working_dir=working_dir)
    except Exception:
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
        if not form.validate_on_submit():
            logger.error(f"Form validation failed: {form.errors}")
            return jsonify({"message": form.errors}), 400

        try:
            logger.info("Creating dataset...")
            create_args = {"form": form, "current_user": current_user}
            dataset = dataset_service.create_from_form(**create_args, allow_empty_package=False)
            logger.info("Created dataset: %s", dataset)
            dataset_service.move_feature_models(dataset)
        except ValueError as e:
            logger.info(f"Validation error while creating dataset: {e}")
            return jsonify({"message": str(e)}), 400
        except Exception:
            logger.exception("Exception while creating dataset")
            error_msg = {"message": "Internal server error while creating dataset"}
            return jsonify(error_msg), 500

        data = {}
        try:
            zenodo_response_json = zenodo_service.create_new_deposition(dataset)
            response_data = json.dumps(zenodo_response_json)
            data = json.loads(response_data)
        except Exception:
            data = {}
            logger.exception("Exception while creating dataset data in Zenodo")

        if data.get("conceptrecid"):
            deposition_id = data.get("id")
            ds_meta_id = dataset.ds_meta_data_id
            dataset_service.update_dsmetadata(ds_meta_id, deposition_id=deposition_id)

            try:
                for feature_model in dataset.feature_models:
                    zenodo_service.upload_file(dataset, deposition_id, feature_model)

                zenodo_service.publish_deposition(deposition_id)
                deposition_doi = zenodo_service.get_doi(deposition_id)
                dataset_service.update_dsmetadata(ds_meta_id, dataset_doi=deposition_doi)

                concept_doi = None
                try:
                    if hasattr(zenodo_service, "get_concept_doi"):
                        concept_doi = zenodo_service.get_concept_doi(deposition_id)
                except Exception:
                    concept_doi = None
                if not concept_doi and deposition_doi:
                    concept_doi = deposition_doi.split(".v")[0]

                if concept_doi:
                    from app import db
                    from app.modules.dataset.models import DataSetConcept

                    concept = DataSetConcept.query.filter_by(conceptual_doi=concept_doi).first()
                    if not concept:
                        concept = DataSetConcept(conceptual_doi=concept_doi)
                        db.session.add(concept)
                        db.session.flush()

                    dataset.ds_concept_id = concept.id
                    db.session.add(dataset)
                    db.session.commit()

            except Exception as e:
                msg = "it has not been possible upload feature models in Zenodo " + f"and update the DOI: {e}"
                return jsonify({"message": msg}), 200

        try:
            follow_service.notify_dataset_published(dataset)
        except Exception:
            current_app.logger.exception("Error sending 'dataset published' notification")

        file_path = current_user.temp_folder()
        if os.path.exists(file_path) and os.path.isdir(file_path):
            shutil.rmtree(file_path)

        msg = "Everything works!"
        return jsonify({"message": msg}), 200

    return render_template("dataset/upload_dataset.html", form=form)


@dataset_bp.route("/dataset/list", methods=["GET", "POST"])
@login_required
def list_dataset():
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

    if not file or not file.filename:
        logger.warning("No file provided in upload request")
        return jsonify({"message": "No file provided"}), 400

    logger.info(f"Received file: {file.filename}")
    filename_lower = file.filename.lower()
    valid_extensions = (".csv", ".txt", ".md")
    if not any(filename_lower.endswith(ext) for ext in valid_extensions):
        logger.warning(f"Invalid file extension: {file.filename}")
        return jsonify({"message": f"Invalid file type. Allowed: {', '.join(valid_extensions)}"}), 400
    if not os.path.exists(temp_folder):
        os.makedirs(temp_folder)

    file_path = os.path.join(temp_folder, file.filename)

    if os.path.exists(file_path):
        base_name, extension = os.path.splitext(file.filename)
        i = 1
        while True:
            candidate_name = f"{base_name} ({i}){extension}"
            candidate = os.path.join(temp_folder, candidate_name)
            if os.path.exists(candidate):
                i += 1
                continue
            new_filename = candidate_name
            break
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
                arc_base = os.path.basename(zip_path[:-4])
                arcname = os.path.join(arc_base, relative_path)
                zipf.write(full_path, arcname=arcname)

    user_cookie = request.cookies.get("download_cookie")
    if not user_cookie:
        user_cookie = str(uuid.uuid4())
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

    existing_record = DSDownloadRecord.query.filter_by(
        user_id=current_user.id if current_user.is_authenticated else None,
        dataset_id=dataset_id,
        download_cookie=user_cookie,
    ).first()

    if not existing_record:
        DSDownloadRecordService().create(
            user_id=current_user.id if current_user.is_authenticated else None,
            dataset_id=dataset_id,
            download_date=datetime.now(timezone.utc),
            download_cookie=user_cookie,
        )

    return resp


@dataset_bp.route("/dataset/<int:dataset_id>/new-version", methods=["GET", "POST"])
@login_required
def create_new_ds_version(dataset_id):
    if request.method == "GET":
        temp_folder = current_user.temp_folder()
        if os.path.exists(temp_folder):
            shutil.rmtree(temp_folder)

    original_dataset = dataset_service.get_or_404(dataset_id)

    if current_user.id != original_dataset.user_id:
        abort(403, "No eres el autor del dataset.")

    form = DataSetVersionForm(obj=original_dataset.ds_meta_data)

    if request.method == "POST":
        if form.validate_on_submit():
            try:
                if form.version_number.data == str(original_dataset.version_number):
                    return jsonify({"message": "The new version number must be different from the original."}), 400

                is_major_from_form = DataSetService.infer_is_major_from_form(form)
                is_valid_version, error_version_msg = DataSetService.check_introduced_version(
                    current_version=str(original_dataset.version_number),
                    form_version=form.version_number.data,
                    is_major=is_major_from_form,
                )
                if not is_valid_version:
                    return jsonify({"message": error_version_msg}), 400

                new_dataset = zenodo_service.publish_new_version(
                    form=form,
                    original_dataset=original_dataset,
                    current_user=current_user,
                    is_major=is_major_from_form,
                )

                target_url = ""
                if new_dataset.ds_meta_data.dataset_doi:
                    target_url = url_for("dataset.subdomain_index", doi=new_dataset.ds_meta_data.dataset_doi)
                else:
                    target_url = url_for("dataset.get_unsynchronized_dataset", dataset_id=new_dataset.id)

                temp_folder = current_user.temp_folder()
                if os.path.exists(temp_folder):
                    shutil.rmtree(temp_folder)

                return jsonify({"message": "Version created successfully", "redirect_url": target_url}), 200

            except Exception:
                logger.exception("Error al crear la nueva versión")
                return jsonify({"message": "Hubo un error interno al publicar la versión."}), 500
        else:
            return jsonify({"message": form.errors}), 400

    form.version_number.data = str(original_dataset.version_number)
    return render_template("dataset/new_version.html", form=form, dataset=original_dataset)


@dataset_bp.route("/doi/<path:doi>/", methods=["GET"])
def subdomain_index(doi):
    new_doi = doi_mapping_service.get_new_doi(doi)
    if new_doi:
        new_url = url_for("dataset.subdomain_index", doi=new_doi)
        return redirect(new_url, code=302)

    current_dataset = None
    concept = dataset_concept_service.filter_by_doi(doi=doi) if dataset_concept_service.filter_by_doi(doi=doi) else None

    if concept:
        if concept.versions:
            current_dataset = concept.versions.first()
        else:
            abort(404)
    else:
        ds_meta_data = dsmetadata_service.filter_latest_by_doi(doi)
        if ds_meta_data:
            current_dataset = ds_meta_data.data_set
            concept = current_dataset.concept
        else:
            abort(404)

    all_versions = concept.versions.all()
    latest_version = all_versions[0] if all_versions else None

    comment_service = CommentService()
    comments = comment_service.get_comments_for_dataset(current_dataset, current_user)

    comment_form = CommentForm()
    user_cookie = ds_view_record_service.create_cookie(dataset=current_dataset)
    resp = make_response(
        render_template(
            "dataset/view_dataset.html",
            dataset=current_dataset,
            all_versions=all_versions,
            latest_version=latest_version,
            conceptual_doi=concept.conceptual_doi,
            comment_form=comment_form,
            comments=comments,
        )
    )
    resp.set_cookie("view_cookie", user_cookie)
    return resp


@dataset_bp.route("/dataset/unsynchronized/<int:dataset_id>/", methods=["GET"])
@login_required
def get_unsynchronized_dataset(dataset_id):
    dataset = dataset_service.get_unsynchronized_dataset(current_user.id, dataset_id)
    if not dataset:
        abort(404)

    if current_user.is_authenticated and current_user.id == dataset.user_id:
        comments = Comment.query.filter_by(dataset_id=dataset.id).order_by(Comment.created_at.desc()).all()
    else:
        comments = (
            Comment.query.filter_by(dataset_id=dataset.id, approved=True).order_by(Comment.created_at.desc()).all()
        )
    comment_form = CommentForm()
    return render_template(
        "dataset/view_dataset.html",
        dataset=dataset,
        comment_form=comment_form,
        comments=comments,
    )


@dataset_bp.route("/dataset/search", methods=["GET", "POST"])
@login_required
def search_dataset():
    filters = {
        "author": request.args.get("author"),
        "affiliation": request.args.get("affiliation"),
        "tags": request.args.get("tags", "").split(","),
        "start_date": request.args.get("start_date"),
        "end_date": request.args.get("end_date"),
        "title": request.args.get("title"),
        "publication_type": request.args.get("publication_type"),
    }
    results = dataset_service.search(**filters)
    return render_template("dataset/search_results.html", datasets=results, filters=filters)


# --- RUTAS CORREGIDAS PARA EDITAR, LOGS Y VERSIONES ---


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
            ds_metadata_edit_log_service.log_multiple_edits(
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


@dataset_bp.route("/dataset/<int:dataset_id>/changelog", methods=["GET"])
@login_required
def view_dataset_changelog(dataset_id):
    dataset = dataset_service.get_or_404(dataset_id)
    logs = ds_metadata_edit_log_service.get_changelog_by_dataset_id(dataset_id)
    return render_template("dataset/changelog.html", dataset=dataset, logs=logs)


@dataset_bp.route("/api/dataset/<int:dataset_id>/changelog", methods=["GET"])
@login_required
def api_dataset_changelog(dataset_id):
    """API endpoint for dataset changelog."""
    dataset = dataset_service.get_or_404(dataset_id)
    edit_logs = ds_metadata_edit_log_service.get_changelog_by_dataset_id(dataset_id)

    return jsonify(
        {
            "dataset_id": dataset_id,
            "dataset_title": dataset.ds_meta_data.title,
            "changelog": [log.to_dict() for log in edit_logs],
        }
    )


@dataset_bp.route("/dataset/<int:dataset_id>/versions", methods=["GET"])
@login_required
def view_dataset_versions(dataset_id):
    dataset = dataset_service.get_or_404(dataset_id)
    versions = []
    if dataset.concept:
        versions = dataset.concept.versions
    return render_template("dataset/versions.html", dataset=dataset, versions=versions)


@dataset_bp.route("/dataset/<int:dataset_id>/republish", methods=["GET", "POST"])
@login_required
def republish_dataset_form(dataset_id):
    return redirect(url_for("dataset.create_new_ds_version", dataset_id=dataset_id))
