from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Dict, List, Optional
from uuid import uuid4

from app import db
from app.modules.fakenodo.models import FakenodoDeposition, FakenodoFile, FakenodoVersion
from app.modules.fakenodo.repositories import (
    FakenodoDepositionRepository,
    FakenodoFileRepository,
    FakenodoVersionRepository,
)
from core.services.BaseService import BaseService


class FakenodoService(BaseService):
    """
    Servicio que simula Zenodo usando la base de datos SQL en lugar de archivos JSON.
    Totalmente compatible con despliegues efímeros (Render, Heroku, etc.).
    """

    def __init__(self, working_dir: Optional[str] = None):
        super().__init__(None)
        self.deposition_repo = FakenodoDepositionRepository()
        self.file_repo = FakenodoFileRepository()
        self.version_repo = FakenodoVersionRepository()

    def create_deposition(self, metadata: Optional[Dict] = None, deposition_id: Optional[int] = None) -> Dict:
        """Crea un nuevo deposition en estado draft.

        Args:
            metadata: Metadata del deposition
            deposition_id: ID específico para el deposition (debe ser el dataset.id)
        """
        # Asegurar que metadata sea un dict si es None
        metadata = metadata or {}

        if deposition_id:
            # Verificar que no existe ya un deposition con este ID
            existing = self.deposition_repo.get_by_id(deposition_id)
            if existing:
                raise ValueError(f"Deposition with ID {deposition_id} already exists")

            # Crear deposition con ID específico usando SQL directo
            # NOTA: Usamos SQL directo para forzar el ID si el autoincrement no cuadra,
            # aunque idealmente deberíamos dejar que la BD maneje los IDs si no es estrictamente necesario forzarlos.
            db.session.execute(
                db.text(
                    "INSERT INTO fakenodo_deposition "
                    "(id, conceptrecid, state, metadata_json, published, dirty, created_at, updated_at) "
                    "VALUES (:id, :conceptrecid, :state, :metadata_json, :published, :dirty, :created_at, :updated_at)"
                ),
                {
                    "id": deposition_id,
                    "conceptrecid": deposition_id,
                    "state": "draft",
                    "metadata_json": json.dumps(metadata),
                    "published": False,
                    "dirty": False,
                    "created_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc),
                },
            )
            db.session.commit()

            # Recuperar el deposition creado
            deposition = self.deposition_repo.get_by_id(deposition_id)
        else:
            # Creación estándar (deja que la BD asigne el ID)
            deposition = FakenodoDeposition(
                conceptrecid=0,  # Se actualizará después con el ID real
                state="draft",
                metadata_json=json.dumps(metadata),
                published=False,
                dirty=False,
            )
            db.session.add(deposition)
            db.session.flush()  # Ejecutar para obtener el ID generado por la BD

            # Actualizar conceptrecid para que coincida con el ID (comportamiento por defecto de fakenodo)
            deposition.conceptrecid = deposition.id
            db.session.commit()

        return self._deposition_to_dict(deposition)

    def list_depositions(self) -> List[Dict]:
        """Lista todos los depositions."""
        depositions = self.deposition_repo.get_all()
        return [self._deposition_to_dict(dep) for dep in depositions]

    def get_deposition(self, deposition_id: int) -> Optional[Dict]:
        """Obtiene un deposition por ID."""
        deposition = self.deposition_repo.get_by_id(deposition_id)
        if not deposition:
            return None
        return self._deposition_to_dict(deposition)

    def delete_deposition(self, deposition_id: int) -> bool:
        """Elimina un deposition y todos sus archivos/versiones."""
        deposition = self.deposition_repo.get_by_id(deposition_id)
        if not deposition:
            return False
        db.session.delete(deposition)
        db.session.commit()
        return True

    def upload_file(self, deposition_id: int, filename: str, content_bytes: Optional[bytes] = None) -> Optional[Dict]:
        """Sube un archivo a un deposition y lo marca como dirty."""
        deposition = self.deposition_repo.get_by_id(deposition_id)
        if not deposition:
            return None

        file = FakenodoFile(
            file_id=str(uuid4()),
            deposition_id=deposition_id,
            name=filename,
            size=len(content_bytes) if content_bytes is not None else 0,
        )
        db.session.add(file)

        deposition.dirty = True
        deposition.updated_at = datetime.now(timezone.utc)
        db.session.commit()

        return file.to_dict()

    def publish_deposition(self, deposition_id: int) -> Optional[Dict]:
        """
        Publica un deposition. Si hay cambios (dirty=True), crea una nueva versión.
        Si no hay cambios, retorna la última versión existente.
        """
        deposition = self.deposition_repo.get_by_id(deposition_id)
        if not deposition:
            return None

        # Obtener última versión
        last_version = (
            FakenodoVersion.query.filter_by(deposition_id=deposition_id)
            .order_by(FakenodoVersion.version.desc())
            .first()
        )

        need_new = last_version is None or deposition.dirty

        if not need_new:
            return last_version.to_dict()

        # Crear nueva versión
        new_version_num = (last_version.version + 1) if last_version else 1
        doi = f"10.1234/fakenodo.{deposition_id}.v{new_version_num}"

        # Snapshot de archivos actuales
        files_snapshot = [file.to_dict() for file in deposition.files]

        version = FakenodoVersion(
            deposition_id=deposition_id,
            version=new_version_num,
            doi=doi,
            metadata_json=deposition.metadata_json,
            files_json=json.dumps(files_snapshot),
        )
        db.session.add(version)

        # Actualizar deposition
        deposition.published = True
        deposition.dirty = False
        deposition.doi = doi
        deposition.state = "published"
        deposition.updated_at = datetime.now(timezone.utc)

        db.session.commit()

        return version.to_dict()

    def list_versions(self, deposition_id: int) -> Optional[List[Dict]]:
        """Lista todas las versiones de un deposition."""
        deposition = self.deposition_repo.get_by_id(deposition_id)
        if not deposition:
            return None

        versions = (
            FakenodoVersion.query.filter_by(deposition_id=deposition_id).order_by(FakenodoVersion.version.asc()).all()
        )

        return [v.to_dict() for v in versions]

    def update_metadata(self, deposition_id: int, metadata: Optional[Dict]) -> Optional[Dict]:
        """
        Actualiza los metadatos de un deposition SIN marcarlo como dirty.
        Editar metadata no genera nueva versión/DOI.
        """
        deposition = self.deposition_repo.get_by_id(deposition_id)
        if not deposition:
            return None

        deposition.metadata_json = json.dumps(metadata or {})
        deposition.updated_at = datetime.now(timezone.utc)
        # NO cambiar dirty flag
        db.session.commit()

        return self._deposition_to_dict(deposition)

    def _deposition_to_dict(self, deposition: FakenodoDeposition) -> Dict:
        """Convierte un deposition a formato dict compatible con Zenodo."""
        metadata = json.loads(deposition.metadata_json) if deposition.metadata_json else {}
        files = [f.to_dict() for f in deposition.files]
        versions = [v.to_dict() for v in deposition.versions]

        return {
            "id": deposition.id,
            "conceptrecid": deposition.conceptrecid,
            "state": deposition.state,
            "metadata": metadata,
            "files": files,
            "versions": versions,
            "published": deposition.published,
            "dirty": deposition.dirty,
            "doi": deposition.doi,
            "links": {
                "self": f"/api/deposit/depositions/{deposition.id}",
                "publish": f"/api/deposit/depositions/{deposition.id}/actions/publish",
            },
            "created_at": deposition.created_at.isoformat() + "Z",
            "updated_at": deposition.updated_at.isoformat() + "Z",
        }
