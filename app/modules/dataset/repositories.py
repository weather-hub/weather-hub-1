import logging
from datetime import datetime, timezone
from typing import Optional

from flask_login import current_user
from sqlalchemy import desc, func

from app.modules.dataset.models import (
    Author,
    DataSet,
    DatasetComment,
    DataSetConcept,
    DOIMapping,
    DSDownloadRecord,
    DSMetaData,
    DSMetaDataEditLog,
    DSViewRecord,
)
from core.repositories.BaseRepository import BaseRepository

logger = logging.getLogger(__name__)


class AuthorRepository(BaseRepository):
    def __init__(self):
        super().__init__(Author)


class DSDownloadRecordRepository(BaseRepository):
    def __init__(self):
        super().__init__(DSDownloadRecord)

    def total_dataset_downloads(self) -> int:
        max_id = self.model.query.with_entities(func.max(self.model.id)).scalar()
        return max_id if max_id is not None else 0


class DataSetConceptRepository(BaseRepository):
    def __init__(self):
        super().__init__(DataSetConcept)

    def ds_concept_by_conceptual_doi(self, doi: str):
        return self.model.query.filter_by(conceptual_doi=doi).first()


class DSMetaDataRepository(BaseRepository):
    def __init__(self):
        super().__init__(DSMetaData)

    def filter_by_doi(self, doi: str) -> Optional[DSMetaData]:
        return self.model.query.filter_by(dataset_doi=doi).first()

    def filter_latest_by_doi(self, doi: str) -> Optional[DSMetaData]:
        return (
            DSMetaData.query.filter(DSMetaData.dataset_doi == doi)
            .join(DataSet, DataSet.ds_meta_data_id == DSMetaData.id)
            .order_by(DataSet.created_at.desc())
            .first()
        )


class DSViewRecordRepository(BaseRepository):
    def __init__(self):
        super().__init__(DSViewRecord)

    def total_dataset_views(self) -> int:
        max_id = self.model.query.with_entities(func.max(self.model.id)).scalar()
        return max_id if max_id is not None else 0

    def the_record_exists(self, dataset: DataSet, user_cookie: str):
        return self.model.query.filter_by(
            user_id=current_user.id if current_user.is_authenticated else None,
            dataset_id=dataset.id,
            view_cookie=user_cookie,
        ).first()

    def create_new_record(self, dataset: DataSet, user_cookie: str) -> DSViewRecord:
        return self.create(
            user_id=current_user.id if current_user.is_authenticated else None,
            dataset_id=dataset.id,
            view_date=datetime.now(timezone.utc),
            view_cookie=user_cookie,
        )


class DataSetRepository(BaseRepository):
    def __init__(self):
        super().__init__(DataSet)

    def get_synchronized(self, current_user_id: int) -> DataSet:
        return (
            self.model.query.join(DSMetaData)
            .filter(DataSet.user_id == current_user_id, DSMetaData.dataset_doi.isnot(None))
            .order_by(self.model.created_at.desc())
            .all()
        )

    def get_unsynchronized(self, current_user_id: int) -> DataSet:
        return (
            self.model.query.join(DSMetaData)
            .filter(DataSet.user_id == current_user_id, DSMetaData.dataset_doi.is_(None))
            .order_by(self.model.created_at.desc())
            .all()
        )

    def get_unsynchronized_dataset(self, current_user_id: int, dataset_id: int) -> DataSet:
        return (
            self.model.query.join(DSMetaData)
            .filter(DataSet.user_id == current_user_id, DataSet.id == dataset_id, DSMetaData.dataset_doi.is_(None))
            .first()
        )

    def count_synchronized_datasets(self):
        # Use an aggregate count to avoid SQLAlchemy selecting all model columns
        # (which fails if the DB schema is missing a column like `dataset_type`).
        return (
            self.model.query.join(DSMetaData)
            .filter(DSMetaData.dataset_doi.isnot(None))
            .with_entities(func.count())
            .scalar()
        )

    def count_unsynchronized_datasets(self):
        # Use an aggregate count to avoid SQLAlchemy selecting all model columns
        # (which fails if the DB schema is missing a column like `dataset_type`).
        return (
            self.model.query.join(DSMetaData)
            .filter(DSMetaData.dataset_doi.is_(None))
            .with_entities(func.count())
            .scalar()
        )

    def latest_synchronized(self):
        return (
            self.model.query.join(DSMetaData)
            .filter(DSMetaData.dataset_doi.isnot(None))
            .order_by(desc(self.model.id))
            .limit(5)
            .all()
        )

    def search(
        self,
        author=None,
        affiliation=None,
        tags=None,
        start_date=None,
        end_date=None,
        title=None,
        publication_type=None,
    ):

        query = self.model.query.join(DSMetaData, isouter=True)
        if author:
            query = query.filter(DSMetaData.authors.ilike(f"%{author}%"))
        if affiliation:
            query = query.filter(DSMetaData.affiliation.ilike(f"%{affiliation}%"))
        if tags:
            for tag in tags:
                query = query.filter(DSMetaData.tags.ilike(f"%{tag.strip()}%"))
        if start_date:
            query = query.filter(DataSet.created_at >= start_date)
        if end_date:
            query = query.filter(DataSet.created_at <= end_date)
        if title:
            query = query.filter(DSMetaData.title.ilike(f"%{title}%"))
        if publication_type:
            query = query.filter(DSMetaData.publication_type == publication_type)

        return query.order_by(DataSet.created_at.desc()).all()


class DOIMappingRepository(BaseRepository):
    def __init__(self):
        super().__init__(DOIMapping)

    def get_new_doi(self, old_doi: str) -> str:
        return self.model.query.filter_by(dataset_doi_old=old_doi).first()


class DSMetaDataEditLogRepository(BaseRepository):
    def __init__(self):
        super().__init__(DSMetaDataEditLog)

    def get_by_ds_meta_data_id(self, ds_meta_data_id: int) -> list:
        """Get all edit logs for a metadata record, ordered by date descending."""
        return self.model.query.filter_by(ds_meta_data_id=ds_meta_data_id).order_by(desc(self.model.edited_at)).all()

    def get_by_dataset_id(self, dataset_id: int) -> list:
        """
        Get all edit logs for a dataset and all its related versions in the same major version.
        For example, if dataset_id is v1.0.1, it will return logs for v1.0.0, v1.0.1, v1.0.2, etc.
        """
        # Obtener el dataset
        dataset = DataSet.query.get(dataset_id)
        if not dataset:
            return []

        # Extraer el major version number (v1.0.0 -> 1, v2.3.4 -> 2)
        version_str = str(dataset.version_number).lstrip("v")
        major_number = version_str.split(".")[0]

        # Encontrar todos los datasets con el mismo major version en el mismo concepto
        datasets_same_major = DataSet.query.filter(
            DataSet.ds_concept_id == dataset.ds_concept_id, DataSet.version_number.like(f"v{major_number}.%")
        ).all()

        # Obtener los ds_meta_data_id de todos esos datasets
        ds_meta_data_ids = [ds.ds_meta_data_id for ds in datasets_same_major]

        # Obtener todos los logs de esos metadata ids
        if not ds_meta_data_ids:
            return []

        return (
            self.model.query.filter(self.model.ds_meta_data_id.in_(ds_meta_data_ids))
            .order_by(desc(self.model.edited_at))
            .all()
        )


class DatasetCommentRepository(BaseRepository):
    def __init__(self):
        super().__init__(DatasetComment)

    def get_by_dataset_id(self, dataset_id: int) -> list:
        """Get all comments for a dataset, ordered by date descending."""
        return self.model.query.filter_by(dataset_id=dataset_id).order_by(desc(self.model.created_at)).all()

    def count_by_dataset_id(self, dataset_id: int) -> int:
        """Count total comments for a dataset."""
        return self.model.query.filter_by(dataset_id=dataset_id).count()

    def get_by_user_id(self, user_id: int) -> list:
        """Get all comments by a user, ordered by date descending."""
        return self.model.query.filter_by(user_id=user_id).order_by(desc(self.model.created_at)).all()
