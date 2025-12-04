import hashlib
import logging
import os
import shutil
import uuid
from typing import Optional

from flask import request

from app.modules.auth.services import AuthenticationService
from app.modules.dataset.models import DataSet, DSMetaData, DSViewRecord
from app.modules.dataset.repositories import (
    AuthorRepository,
    DataSetConceptRepository,
    DataSetRepository,
    DOIMappingRepository,
    DSDownloadRecordRepository,
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
                # If the file isn't in the user's temp folder, warn and continue.
                logger.warning(f"Source file not found, skipping move: {src_path}")
                continue
            try:
                # If destination file already exists, remove it (overwrite behaviour).
                if os.path.exists(dst_path):
                    logger.info(f"Destination file {dst_path} exists — removing before move.")
                    os.remove(dst_path)

                shutil.move(src_path, dst_path)
            except Exception as exc:
                # Log and raise so upstream code can handle rollback if needed.
                logger.exception(f"Failed moving file {src_path} to {dst_path}: {exc}")
                raise

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
            # llenalo con los nombres de los ficheros que componen el paquete
            uploaded_filenames = []
            for feature_model in form.feature_models:
                filename = feature_model.filename.data
                fmmetadata = self.fmmetadata_repository.create(commit=False, **feature_model.get_fmmetadata())
                for author_data in feature_model.get_authors():
                    author = self.author_repository.create(commit=False, fm_meta_data_id=fmmetadata.id, **author_data)
                    fmmetadata.authors.append(author)

                fm = self.feature_model_repository.create(
                    commit=False, data_set_id=dataset.id, fm_meta_data_id=fmmetadata.id
                )
                uploaded_filenames.append(feature_model.filename.data)

            file_paths = [os.path.join(current_user.temp_folder(), fn) for fn in uploaded_filenames]
            try:
                # Si tu flujo es que en create_from_form se añaden varios archivos por feature model,
                # asegúrate de pasar aquí la lista completa de paths para validar juntos.
                validate_dataset_package(
                    # o la lista completa de archivos del paquete
                    # o True si quieres forzar EXACTAMENTE esas columnas
                    file_paths=file_paths,
                    allow_empty=allow_empty_package,
                )
            except Exception:
                # rollback y propaga error (tu código ya maneja rollback en el except general)
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
        """Devuelve True si el formulario contiene al menos un feature model (archivos subidos)."""
        try:
            return bool(getattr(form, "feature_models", [])) and len(form.feature_models) > 0
        except Exception:
            return False

    @staticmethod
    def check_introduced_version(current_version: str, is_major: bool, form_version: str) -> tuple[bool, str]:
        """Calcula la siguiente versión basada en la versión actual y si es una versión mayor."""
        clean_current = current_version.lstrip("v")
        clean_form_version = form_version.lstrip("v")
        current_parts = clean_current.split(".")
        form_parts = clean_form_version.split(".")
        is_valid = True
        error_message = ""

        if len(current_parts) != 3 or len(form_parts) != 3:
            is_valid = False
            error_message = "Version format must be X.Y.Z where X, Y, and Z are integers."
            return is_valid, error_message

        major_current, minor_current, patch_current = map(int, current_parts)
        major_form, minor_form, patch_form = map(int, form_parts)
        if is_major:
            if major_form <= major_current:
                is_valid = False
                error_message = "For a major version, the major version must be increased.(Ej: 1.0.0 to 2.0.0)"
            if minor_form != 0 or patch_form != 0:
                is_valid = False
                error_message = "For a major version, minor and patch versions must be zero.(Ej: 1.0.0 to 2.0.0)"
        else:
            if major_form > major_current:
                is_valid = False
                error_message = "For a non-major version, the major version cannot be increased."
            if minor_form <= minor_current and patch_form <= patch_current:
                is_valid = False
                error_message = "For a non-major version, minor or patch version must be increased."

        return is_valid, error_message


class AuthorService(BaseService):
    def __init__(self):
        super().__init__(AuthorRepository())


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
