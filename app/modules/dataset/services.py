import hashlib
import logging
import os
import shutil
import uuid
from typing import Optional

from flask import request

from app.modules.auth.services import AuthenticationService
from app.modules.dataset.models import DataSet, DSMetaData, DSMetaDataEditLog, DSViewRecord
from app.modules.dataset.repositories import (
    AuthorRepository,
    DataSetConceptRepository,
    DataSetRepository,
    DOIMappingRepository,
    DSDownloadRecordRepository,
    DSMetaDataEditLogRepository,
    DSMetaDataRepository,
    DSViewRecordRepository,
)
from app.modules.dataset.validator import validate_dataset_package
from app.modules.featuremodel.repositories import FeatureModelRepository, FMMetaDataRepository
from app.modules.hubfile.repositories import (
    HubfileDownloadRecordRepository,
    HubfileRepository,
    HubfileViewRecordRepository,
)
from app.modules.zenodo.services import ZenodoService
from core.services.BaseService import BaseService

logger = logging.getLogger(__name__)


def calculate_checksum_and_size(file_path):
    file_size = os.path.getsize(file_path)
    with open(file_path, "rb") as file:
        content = file.read()
        hash_hex = hashlib.sha256(content).hexdigest()
        return hash_hex, file_size


class DataSetService(BaseService):
    def __init__(self):
        super().__init__(DataSetRepository())
        self.feature_model_repository = FeatureModelRepository()
        self.author_repository = AuthorRepository()
        self.dsmetadata_repository = DSMetaDataRepository()
        self.fmmetadata_repository = FMMetaDataRepository()
        self.dsdownloadrecord_repository = DSDownloadRecordRepository()
        self.hubfiledownloadrecord_repository = HubfileDownloadRecordRepository()
        self.hubfilerepository = HubfileRepository()
        self.dsviewrecord_repostory = DSViewRecordRepository()
        self.hubfileviewrecord_repository = HubfileViewRecordRepository()
        self.dsmetadata_service = DSMetaDataService()
        self.zenodo_service = ZenodoService()
        self.ds_metadata_edit_log_service = DSMetaDataEditLogService()

    def move_feature_models(self, dataset: DataSet):
        current_user = AuthenticationService().get_authenticated_user()
        source_dir = current_user.temp_folder()

        working_dir = os.getenv("WORKING_DIR", "")
        dest_dir = os.path.join(
            working_dir,
            "uploads",
            f"user_{current_user.id}",
            f"dataset_{dataset.id}",
        )

        os.makedirs(dest_dir, exist_ok=True)

        for feature_model in dataset.feature_models:
            filename = feature_model.fm_meta_data.filename
            src_path = os.path.join(source_dir, filename)
            dst_path = os.path.join(dest_dir, filename)

            if not os.path.exists(src_path):
                logger.warning(f"Source file not found, skipping move: {src_path}")
                continue
            try:
                if os.path.exists(dst_path):
                    logger.info(f"Destination file {dst_path} exists — removing before move.")
                    os.remove(dst_path)

                shutil.move(src_path, dst_path)
            except Exception as exc:
                logger.exception(f"Failed moving file {src_path} to {dst_path}: {exc}")
                raise

    def copy_feature_models_from_original(self, new_dataset: DataSet, original_dataset: DataSet):
        """
        Copia los feature models del dataset original al nuevo dataset.
        Esto es necesario cuando se crea una nueva versión para que los archivos persistan.
        Incluye la copia de metadata, archivos físicos y registros Hubfile.
        """
        from app import db
        from app.modules.featuremodel.models import FeatureModel, FMMetaData
        from app.modules.hubfile.models import Hubfile

        working_dir = os.getenv("WORKING_DIR", "")

        # Directorios de origen y destino
        src_dir = os.path.join(
            working_dir,
            "uploads",
            f"user_{original_dataset.user_id}",
            f"dataset_{original_dataset.id}",
        )

        dest_dir = os.path.join(
            working_dir,
            "uploads",
            f"user_{new_dataset.user_id}",
            f"dataset_{new_dataset.id}",
        )

        os.makedirs(dest_dir, exist_ok=True)

        # Copiar cada feature model
        for original_fm in original_dataset.feature_models:
            # Copiar metadata
            new_fm_meta = FMMetaData(
                filename=original_fm.fm_meta_data.filename,
                title=original_fm.fm_meta_data.title,
                description=original_fm.fm_meta_data.description,
                publication_type=original_fm.fm_meta_data.publication_type,
                publication_doi=original_fm.fm_meta_data.publication_doi,
                tags=original_fm.fm_meta_data.tags,
                version=original_fm.fm_meta_data.version,
            )
            db.session.add(new_fm_meta)
            db.session.flush()

            # Copiar feature model
            new_fm = FeatureModel(
                data_set_id=new_dataset.id,
                fm_meta_data_id=new_fm_meta.id,
            )
            db.session.add(new_fm)
            db.session.flush()

            # Copiar registros Hubfile (necesario para get_files_count())
            for original_hubfile in original_fm.files:
                new_hubfile = Hubfile(
                    name=original_hubfile.name,
                    checksum=original_hubfile.checksum,
                    size=original_hubfile.size,
                    feature_model_id=new_fm.id,
                )
                db.session.add(new_hubfile)
                logger.info(f"Copied Hubfile record: {original_hubfile.name} (size: {original_hubfile.size})")

            # Copiar archivo físico
            src_file = os.path.join(src_dir, original_fm.fm_meta_data.filename)
            dest_file = os.path.join(dest_dir, original_fm.fm_meta_data.filename)

            if os.path.exists(src_file):
                try:
                    shutil.copy2(src_file, dest_file)
                    logger.info(f"Copied feature model file: {src_file} -> {dest_file}")
                except Exception as exc:
                    logger.exception(f"Failed copying file {src_file} to {dest_file}: {exc}")
            else:
                logger.warning(f"Source feature model file not found: {src_file}")

        db.session.commit()
        logger.info(
            f"Copied {len(original_dataset.feature_models)} feature models "
            + f"from dataset {original_dataset.id} to {new_dataset.id}"
        )

    def get_synchronized(self, current_user_id: int) -> DataSet:
        return self.repository.get_synchronized(current_user_id)

    def get_unsynchronized(self, current_user_id: int) -> DataSet:
        return self.repository.get_unsynchronized(current_user_id)

    def get_unsynchronized_dataset(self, current_user_id: int, dataset_id: int) -> DataSet:
        return self.repository.get_unsynchronized_dataset(current_user_id, dataset_id)

    def latest_synchronized(self):
        return self.repository.latest_synchronized()

    def count_synchronized_datasets(self):
        return self.repository.count_synchronized_datasets()

    def count_feature_models(self):
        return self.feature_model_service.count_feature_models()

    def count_authors(self) -> int:
        return self.author_repository.count()

    def count_dsmetadata(self) -> int:
        return self.dsmetadata_repository.count()

    def total_dataset_downloads(self) -> int:
        return self.dsdownloadrecord_repository.total_dataset_downloads()

    def total_dataset_views(self) -> int:
        return self.dsviewrecord_repostory.total_dataset_views()

    def create_from_form(self, form, current_user, allow_empty_package: bool = False) -> DataSet:
        main_author = {
            "name": f"{current_user.profile.surname}, {current_user.profile.name}",
            "affiliation": current_user.profile.affiliation,
            "orcid": current_user.profile.orcid,
        }
        try:
            logger.info(f"Creating dsmetadata...: {form.get_dsmetadata()}")
            form_vnumber = form.get_version_number()
            dsmetadata = self.dsmetadata_repository.create(**form.get_dsmetadata())
            for author_data in [main_author] + form.get_authors():
                author = self.author_repository.create(commit=False, ds_meta_data_id=dsmetadata.id, **author_data)
                dsmetadata.authors.append(author)

            dataset = self.create(
                commit=False, user_id=current_user.id, ds_meta_data_id=dsmetadata.id, version_number=form_vnumber
            )

            uploaded_filenames = []
            for csv_file_form in form.feature_models:
                filename = csv_file_form.filename.data
                fmmetadata_data = csv_file_form.get_fmmetadata()

                fmmetadata = self.fmmetadata_repository.create(commit=False, **fmmetadata_data)
                for author_data in csv_file_form.get_authors():
                    author = self.author_repository.create(commit=False, fm_meta_data_id=fmmetadata.id, **author_data)
                    fmmetadata.authors.append(author)

                fm = self.feature_model_repository.create(
                    commit=False, data_set_id=dataset.id, fm_meta_data_id=fmmetadata.id
                )
                uploaded_filenames.append(csv_file_form.filename.data)

            file_paths = [os.path.join(current_user.temp_folder(), fn) for fn in uploaded_filenames]
            try:
                validate_dataset_package(
                    file_paths=file_paths,
                    allow_empty=allow_empty_package,
                )
            except Exception:
                self.repository.session.rollback()
                raise

            for e in range(0, len(uploaded_filenames)):
                filename = uploaded_filenames[e]
                file_path = file_paths[e]
                checksum, size = calculate_checksum_and_size(file_path)

                file = self.hubfilerepository.create(
                    commit=False, name=filename, checksum=checksum, size=size, feature_model_id=fm.id
                )
                fm.files.append(file)
            self.repository.session.commit()
        except Exception as exc:
            logger.info(f"Exception creating dataset from form...: {exc}")
            self.repository.session.rollback()
            raise exc
        return dataset

    def update_dsmetadata(self, id, **kwargs):
        return self.dsmetadata_repository.update(id, **kwargs)

    def get_uvlhub_doi(self, dataset: DataSet) -> str:
        domain = os.getenv("DOMAIN", "localhost")
        return f"http://{domain}/doi/{dataset.ds_meta_data.dataset_doi}"

    def get_conceptual_doi(self, dataset: DataSet) -> str:
        domain = os.getenv("DOMAIN", "localhost")
        return f"http://{domain}/doi/{dataset.concept.conceptual_doi}" if dataset.concept else None

    def search(self, **filters):
        return self.repository.search(**filters)

    @staticmethod
    def infer_is_major_from_form(form) -> bool:
        """
        Determina si es major version comparando números de versión.
        Major version: incrementa el primer número (1.0.0 -> 2.0.0)
        Minor version: incrementa segundo o tercer número (1.0.0 -> 1.1.0 o 1.0.1)

        DEPRECATED: Esta lógica es incorrecta. Use infer_is_major_from_versions() en su lugar.
        """
        try:
            return bool(getattr(form, "feature_models", [])) and len(form.feature_models) > 0
        except Exception:
            return False

    @staticmethod
    def check_introduced_version(current_version: str, is_major: bool, form_version: str) -> tuple[bool, str]:
        clean_current = current_version.lstrip("v")
        clean_form_version = form_version.lstrip("v")
        current_parts = clean_current.split(".")
        form_parts = clean_form_version.split(".")
        is_valid = True
        error_message = ""

        if len(current_parts) != 3 or len(form_parts) != 3:
            return False, "Version format must be X.Y.Z where X, Y, and Z are integers."

        for part in form_parts:
            if len(part) > 1 and part.startswith("0"):
                return False, "Version components must not contain leading zeros.(Ej: 01)"

        major_current, minor_current, patch_current = map(int, current_parts)
        major_form, minor_form, patch_form = map(int, form_parts)
        if is_major:
            if major_form <= major_current:
                is_valid = False
                error_message = "For a major version, the major version must be increased.(Ej: 1.0.0 to 2.0.0)"
            if minor_form != 0 or patch_form != 0:
                is_valid = False
                error_message = "For a major version, minor and patch versions must be zero.(Ej: 1.0.0 to 2.0.0)"
            if major_form > major_current + 1:
                is_valid = False
                error_message = "Major version can only be increased by one at a time."
        else:
            if major_form > major_current:
                is_valid = False
                error_message = "For a non-major version, the major version cannot be increased."
            if minor_form <= minor_current and patch_form <= patch_current:
                is_valid = False
                error_message = "For a non-major version, minor or patch version must be increased."
            if minor_form > minor_current + 1 or patch_form > patch_current + 1:
                is_valid = False
                error_message = "Minor or patch version can only be increased by one at a time."

        return is_valid, error_message

    @staticmethod
    def check_upload_version(version: str) -> tuple[bool, str]:
        clean_version = version.lstrip("v")
        version_parts = clean_version.split(".")

        if len(version_parts) != 3:
            return False, "Version format must be X.Y.Z where X, Y, and Z are integers."

        for part in version_parts:
            if not part.isdigit():
                return False, "Version components must be integers."
            if len(part) > 1 and part.startswith("0"):
                return False, "Version components must not contain leading zeros.(Ej: 01)"

        return True, ""


class AuthorService(BaseService):
    def __init__(self):
        super().__init__(AuthorRepository())

    @staticmethod
    def get_unique_authors(dataset: DataSet) -> list:
        unique_authors = {}
        for author in dataset.ds_meta_data.authors:
            key = (author.name, author.affiliation, author.orcid)
            if key not in unique_authors:
                unique_authors[key] = author
        return list(unique_authors.values())


class DSDownloadRecordService(BaseService):
    def __init__(self):
        super().__init__(DSDownloadRecordRepository())


class DataSetConceptService(BaseService):
    def __init__(self):
        super().__init__(DataSetConceptRepository())

    def filter_by_doi(self, doi: str):
        return self.repository.ds_concept_by_conceptual_doi(doi)

    def update(self, id, **kwargs):
        return self.repository.update(id, **kwargs)


class DSMetaDataService(BaseService):
    def __init__(self):
        super().__init__(DSMetaDataRepository())

    def update(self, id, **kwargs):
        return self.repository.update(id, **kwargs)

    def filter_by_doi(self, doi: str) -> Optional[DSMetaData]:
        return self.repository.filter_by_doi(doi)

    def filter_latest_by_doi(self, doi: str) -> Optional[DSMetaData]:
        return self.repository.filter_latest_by_doi(doi)


class DSViewRecordService(BaseService):
    def __init__(self):
        super().__init__(DSViewRecordRepository())

    def the_record_exists(self, dataset: DataSet, user_cookie: str):
        return self.repository.the_record_exists(dataset, user_cookie)

    def create_new_record(self, dataset: DataSet, user_cookie: str) -> DSViewRecord:
        return self.repository.create_new_record(dataset, user_cookie)

    def create_cookie(self, dataset: DataSet) -> str:
        user_cookie = request.cookies.get("view_cookie")
        if not user_cookie:
            user_cookie = str(uuid.uuid4())

        existing_record = self.the_record_exists(dataset=dataset, user_cookie=user_cookie)

        if not existing_record:
            self.create_new_record(dataset=dataset, user_cookie=user_cookie)

        return user_cookie


class DOIMappingService(BaseService):
    def __init__(self):
        super().__init__(DOIMappingRepository())

    def get_new_doi(self, old_doi: str) -> str:
        doi_mapping = self.repository.get_new_doi(old_doi)
        if doi_mapping:
            return doi_mapping.dataset_doi_new
        else:
            return None


class SizeService:
    def __init__(self):
        pass

    def get_human_readable_size(self, size: int) -> str:
        if size < 1024:
            return f"{size} bytes"
        elif size < 1024**2:
            return f"{round(size / 1024, 2)} KB"
        elif size < 1024**3:
            return f"{round(size / (1024 ** 2), 2)} MB"
        else:
            return f"{round(size / (1024 ** 3), 2)} GB"


class DSMetaDataEditLogService(BaseService):
    def __init__(self):
        super().__init__(DSMetaDataEditLogRepository())

    def log_edit(
        self,
        ds_meta_data_id: int,
        user_id: int,
        field_name: str,
        old_value: str,
        new_value: str,
        change_summary: str = None,
    ) -> DSMetaDataEditLog:
        return self.repository.create(
            ds_meta_data_id=ds_meta_data_id,
            user_id=user_id,
            field_name=field_name,
            old_value=old_value,
            new_value=new_value,
            change_summary=change_summary,
        )

    def log_multiple_edits(self, ds_meta_data_id: int, user_id: int, changes: list) -> list:
        logs = []
        for change in changes:
            log = self.log_edit(
                ds_meta_data_id=ds_meta_data_id,
                user_id=user_id,
                field_name=change.get("field"),
                old_value=change.get("old"),
                new_value=change.get("new"),
                change_summary=change.get("summary"),
            )
            logs.append(log)
        return logs

    def get_changelog(self, ds_meta_data_id: int) -> list:
        return self.repository.get_by_ds_meta_data_id(ds_meta_data_id)

    def get_changelog_by_dataset_id(self, dataset_id: int) -> list:
        return self.repository.get_by_dataset_id(dataset_id)
