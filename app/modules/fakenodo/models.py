from datetime import datetime, timezone

from app import db


class FakenodoDeposition(db.Model):
    """
    Representa un deposition en Fakenodo (equivalente a Zenodo).
    Almacena el concepto completo con todas sus versiones.
    """

    __tablename__ = "fakenodo_deposition"

    id = db.Column(db.Integer, primary_key=True)
    conceptrecid = db.Column(db.Integer, nullable=False)  # En Fakenodo, igual que id
    state = db.Column(db.String(50), nullable=False, default="draft")  # draft | published
    metadata_json = db.Column(db.Text)  # JSON serializado con metadata
    published = db.Column(db.Boolean, default=False)
    dirty = db.Column(db.Boolean, default=False)  # Indica si hay cambios sin publicar
    doi = db.Column(db.String(120))  # DOI de la última versión
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    # Relaciones
    files = db.relationship("FakenodoFile", backref="deposition", lazy=True, cascade="all, delete-orphan")
    versions = db.relationship("FakenodoVersion", backref="deposition", lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f"FakenodoDeposition<id={self.id}, state={self.state}, doi={self.doi}>"


class FakenodoFile(db.Model):
    """
    Representa un archivo subido a un deposition.
    """

    __tablename__ = "fakenodo_file"

    id = db.Column(db.Integer, primary_key=True)
    file_id = db.Column(db.String(120), nullable=False, unique=True)  # UUID
    deposition_id = db.Column(db.Integer, db.ForeignKey("fakenodo_deposition.id"), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    size = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "id": self.file_id,
            "name": self.name,
            "size": self.size,
            "created_at": self.created_at.isoformat() + "Z",
        }

    def __repr__(self):
        return f"FakenodoFile<id={self.file_id}, name={self.name}>"


class FakenodoVersion(db.Model):
    """
    Representa una versión publicada de un deposition.
    Cada vez que se publica, se crea un snapshot inmutable.
    """

    __tablename__ = "fakenodo_version"

    id = db.Column(db.Integer, primary_key=True)
    deposition_id = db.Column(db.Integer, db.ForeignKey("fakenodo_deposition.id"), nullable=False)
    version = db.Column(db.Integer, nullable=False)  # 1, 2, 3...
    doi = db.Column(db.String(120), nullable=False, unique=True)
    metadata_json = db.Column(db.Text)  # Snapshot de metadata en esta versión
    files_json = db.Column(db.Text)  # Snapshot de archivos en esta versión (JSON array)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        import json

        return {
            "version": self.version,
            "doi": self.doi,
            "metadata": json.loads(self.metadata_json) if self.metadata_json else {},
            "files": json.loads(self.files_json) if self.files_json else [],
            "created_at": self.created_at.isoformat() + "Z",
        }

    def __repr__(self):
        return f"FakenodoVersion<deposition_id={self.deposition_id}, version={self.version}, doi={self.doi}>"
