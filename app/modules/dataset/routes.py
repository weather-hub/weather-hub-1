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
    DatasetCommentService,
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

        # Mover los feature models nuevos que haya subido el usuario (si hay)
        logger.info(
            f"[VERSIONING] New dataset {new_dataset.id} created."
            + f" Feature models uploaded by user: {len(new_dataset.feature_models)}"
        )
        _dataset_service.move_feature_models(new_dataset)
        logger.info(f"[VERSIONING] After move_feature_models: {len(new_dataset.feature_models)} files")

        # SIEMPRE copiar archivos del dataset original
        # Esto permite que las nuevas versiones tengan todos los archivos anteriores
        # más cualquier archivo nuevo que el usuario haya subido
        logger.info(
            f"[VERSIONING] Original dataset {original_dataset.id} has {len(original_dataset.feature_models)} files"
        )
        logger.info(
            f"[VERSIONING] Starting copy from original dataset {original_dataset.id} to new version {new_dataset.id}"
        )
        _dataset_service.copy_feature_models_from_original(new_dataset, original_dataset)

        # Refrescar dataset para ver archivos copiados
        from app import db

        db.session.refresh(new_dataset)
        logger.info(
            f"[VERSIONING] After copy_feature_models_from_original: {len(new_dataset.feature_models)} files total"
        )

        # Reutilizar el deposition existente en lugar de crear uno nuevo
        # Todas las versiones de un concepto comparten el mismo deposition
        original_deposition_id = original_dataset.ds_meta_data.deposition_id

        if original_deposition_id:
            # Reutilizar deposition existente
            deposition_id = original_deposition_id
        else:
            # Fallback: crear nuevo si el original no tiene deposition (datos legacy)
            data = self.create_new_deposition(new_dataset)
            deposition_id = data.get("id")

        for feature_model in new_dataset.feature_models:
            self.upload_file(new_dataset, deposition_id, feature_model)

        # CRÍTICO: Solo crear nueva versión de DOI si es major version
        self.publish_deposition(deposition_id, is_major=is_major)
        new_doi = self.get_doi(deposition_id)

        # Para major version: nuevo DOI. Para minor: mismo DOI del original
        if not is_major and original_dataset.ds_meta_data.dataset_doi:
            # Minor version: mantener el DOI del original
            new_doi = original_dataset.ds_meta_data.dataset_doi
            logger.info(f"[VERSIONING] Minor version - reusing DOI: {new_doi}")

            # Registrar la creación de la minor version en el changelog
            # El repositorio se encarga de agrupar todos los logs de la misma major version
            from datetime import datetime, timezone

            from app.modules.dataset.models import DSMetaDataEditLog

            # Detectar qué cambió entre versiones
            if original_dataset.ds_meta_data.title != new_dataset.ds_meta_data.title:
                DSMetaDataEditLog.create_new_DSMetaDataEditLog(
                    ds_meta_data_id=new_dataset.ds_meta_data_id,
                    user_id=current_user.id,
                    edited_at=datetime.now(timezone.utc),
                    field_name="title",
                    old_value=original_dataset.ds_meta_data.title,
                    new_value=new_dataset.ds_meta_data.title,
                )
            if original_dataset.ds_meta_data.description != new_dataset.ds_meta_data.description:
                DSMetaDataEditLog.create_new_DSMetaDataEditLog(
                    ds_meta_data_id=new_dataset.ds_meta_data_id,
                    user_id=current_user.id,
                    edited_at=datetime.now(timezone.utc),
                    field_name="description",
                    old_value=original_dataset.ds_meta_data.description,
                    new_value=new_dataset.ds_meta_data.description,
                )

            if original_dataset.ds_meta_data.tags != new_dataset.ds_meta_data.tags:
                DSMetaDataEditLog.create_new_DSMetaDataEditLog(
                    ds_meta_data_id=new_dataset.ds_meta_data_id,
                    user_id=current_user.id,
                    edited_at=datetime.now(timezone.utc),
                    field_name="tags",
                    old_value=original_dataset.ds_meta_data.tags,
                    new_value=new_dataset.ds_meta_data.tags,
                )

            changelog_entry = DSMetaDataEditLog(
                ds_meta_data_id=new_dataset.ds_meta_data_id,
                user_id=current_user.id,
                edited_at=datetime.now(timezone.utc),
                field_name="version",
                old_value=str(original_dataset.version_number),
                new_value=str(new_dataset.version_number),
                change_summary=None,
            )
            db.session.add(changelog_entry)
            db.session.commit()
            logger.info(f"[VERSIONING] Changelog entry created for minor version {new_dataset.version_number}")
        else:
            logger.info(f"[VERSIONING] Major version - new DOI: {new_doi}")

        _dataset_service.update_dsmetadata(
            new_dataset.ds_meta_data_id, deposition_id=deposition_id, dataset_doi=new_doi
        )
        return new_dataset

    def create_new_deposition(self, dataset) -> dict:
        self.dataset_id = getattr(dataset, "id", None)
        metadata = {"title": getattr(dataset, "title", f"dataset-{self.dataset_id}")}
        # Forzar que deposition_id = dataset.id para consistencia
        rec = self.service.create_deposition(metadata=metadata, deposition_id=self.dataset_id)
        return {
            "id": rec["id"],
            "conceptrecid": rec.get("conceptrecid"),
            "conceptid": rec.get("conceptid"),
            "conceptdoi": rec.get("conceptdoi"),  # CRÍTICO 2: Incluir conceptdoi
            "metadata": rec.get("metadata", {}),
        }

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

    def publish_deposition(self, deposition_id, is_major=True):
        """Publica deposition. Si is_major=False, no crea nueva versión de DOI."""
        version = self.service.publish_deposition(deposition_id, is_major=is_major)
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
        cdoi = rec["conceptdoi"]
        if cdoi:
            return cdoi
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

        version_check, version_message = DataSetService.check_upload_version(str(form.version_number.data))
        if not version_check:
            logger.error(f"Version check failed: {version_message}")
            return jsonify({"message": version_message}), 400

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

                # Obtener concept_doi del deposition, NUNCA derivar
                concept_doi = None
                try:
                    if hasattr(zenodo_service, "get_concept_doi"):
                        concept_doi = zenodo_service.get_concept_doi(deposition_id)
                except Exception:
                    logger.exception("Failed to get concept DOI from zenodo service")
                    concept_doi = None

                # Si no se pudo obtener, crear uno basado en deposition_id como fallback
                if not concept_doi:
                    concept_doi = f"10.1234/concept.{deposition_id}"
                    logger.warning(f"Could not get concept DOI from deposition, using fallback: {concept_doi}")

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
        datasets = dataset_service.get_synchronized(current_user.id)
        dataset_to_show = [ds for ds in datasets if ds.is_latest]
    except Exception:
        communities = []

    return render_template(
        "dataset/list_datasets.html",
        datasets=dataset_to_show,
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
    original_dataset = dataset_service.get_or_404(dataset_id)
    if current_user.id != original_dataset.user_id:
        abort(403, "No eres el autor del dataset.")
    if not original_dataset.is_latest:
        abort(403, "Solo se pueden crear nuevas versiones a partir de la última versión del dataset.")

    if request.method == "GET":
        temp_folder = current_user.temp_folder()
        if os.path.exists(temp_folder):
            shutil.rmtree(temp_folder)

    meta_data_obj = original_dataset.ds_meta_data
    meta_data_obj.authors = []
    form = DataSetVersionForm(obj=meta_data_obj)

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

    # Cargar datos del dataset original en el formulario
    form.version_number.data = str(original_dataset.version_number)
    form.title.data = original_dataset.ds_meta_data.title
    form.desc.data = original_dataset.ds_meta_data.description
    form.publication_type.data = original_dataset.ds_meta_data.publication_type.value
    form.publication_doi.data = original_dataset.ds_meta_data.publication_doi
    form.tags.data = original_dataset.ds_meta_data.tags

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

    if not concept:
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
            authors=AuthorService.get_unique_authors(current_dataset),
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


@dataset_bp.route("/dataset/<int:dataset_id>/changelog", methods=["GET"])
@login_required
def view_dataset_changelog(dataset_id):
    dataset = dataset_service.get_or_404(dataset_id)
    # Obtener logs ordenados del más antiguo al más reciente para agruparlos correctamente
    logs_chronological = ds_metadata_edit_log_service.get_changelog_by_dataset_id(dataset_id)

    version_groups = []
    current_group = None

    for log in logs_chronological:
        if log.field_name == "version":
            # Si hay un grupo anterior, lo guardamos
            if current_group:
                version_groups.append(current_group)

            # Empezamos un nuevo grupo con este cambio de versión
            current_group = {
                "from_version": log.old_value,
                "to_version": log.new_value,
                "user": log.user,
                "edited_at": log.edited_at,
                "changes": [],  # Aquí irán los cambios de título, descripción, etc.
            }
        elif current_group:
            # Si no es un log de versión, es un cambio asociado al grupo actual
            current_group["changes"].append(log)

    # No olvidar añadir el último grupo a la lista
    if current_group:
        version_groups.append(current_group)

    # Invertimos la lista para mostrar los grupos más recientes primero
    version_groups.reverse()

    return render_template("dataset/changelog.html", dataset=dataset, version_groups=version_groups)


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
        comment = comment_service.create_comment(dataset_id=dataset_id, user_id=current_user.id, content=content)

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
