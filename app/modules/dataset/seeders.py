import json
import uuid
from datetime import datetime, timedelta, timezone

from app.modules.dataset.models import (
    Author,
    DataSet,
    DataSetConcept,
    DSMetaData,
    DSMetrics,
    PublicationType,
)
from app.modules.fakenodo.models import FakenodoDeposition, FakenodoFile, FakenodoVersion
from app.modules.featuremodel.models import FeatureModel, FMMetaData, FMMetrics
from app.modules.hubfile.models import Hubfile
from core.seeders.BaseSeeder import BaseSeeder


class DatasetSeeder(BaseSeeder):
    """
    Seeder completo para datasets que crea:
    - Datasets con múltiples versiones
    - Conceptos de datasets (para versionado)
    - Depositions en Fakenodo con versiones publicadas
    - Feature models y archivos asociados
    - DOIs conceptuales y de versión
    """

    priority = 15  # Ejecutar después de AuthSeeder y RolesSeeder

    def run(self):
        # Verificar que existen usuarios
        from app.modules.auth.repositories import UserRepository

        user_repo = UserRepository()
        user1 = user_repo.get_by_email("user1@example.com")
        user2 = user_repo.get_by_email("user2@example.com")

        if not user1 or not user2:
            print("⚠️ Warning: Users not found. Run AuthSeeder first.")
            return

        print("🌱 Seeding datasets with versions and Fakenodo depositions...")

        # === DATASET 1: Weather Patterns Dataset (3 versiones) ===
        self._create_weather_patterns_dataset(user1)

        # === DATASET 2: Climate Analysis Dataset (2 versiones) ===
        self._create_climate_analysis_dataset(user2)

        # === DATASET 3: Single version dataset ===
        self._create_simple_dataset(user1)

        print("✅ Dataset seeding completed successfully!")

    def _create_weather_patterns_dataset(self, user):
        """Crea un dataset con 3 versiones en Fakenodo"""

        # 1. Crear concepto de dataset con DOI conceptual
        concept_doi = "10.1234/fakenodo.concept.1001"
        concept = DataSetConcept(conceptual_doi=concept_doi)
        self.seed([concept])

        # 2. Crear deposition en Fakenodo
        deposition_id = 1001
        deposition = FakenodoDeposition(
            id=deposition_id,
            conceptrecid=str(deposition_id),
            conceptdoi=concept_doi,
            state="published",
            published=True,
            dirty=False,
            doi=f"10.1234/fakenodo.{deposition_id}.2",  # DOI de la última versión (v2.0.0)
            created_at=datetime.now(timezone.utc) - timedelta(days=90),
            updated_at=datetime.now(timezone.utc),
        )
        self.seed([deposition])

        # 3. Crear 3 versiones del dataset
        # Nota: v1.0.0 y v1.1.0 comparten el mismo DOI (version_num=1)
        # v2.0.0 obtiene un nuevo DOI (version_num=2)
        # Solo se crea una entrada en fakenodo_version por cada versión mayor
        versions_data = [
            {
                "version": "v1.0.0",
                "version_num": 1,  # DOI: .1001.1
                "create_fakenodo_version": False,  # No crear aún
                "title": "Weather Patterns Dataset",
                "description": "Initial release of weather patterns data from multiple stations",
                "days_ago": 90,
                "num_models": "100",
                "num_features": "250",
                "files": [
                    {"name": "weather_data_2020.uvl", "size": 1024 * 500},
                    {"name": "metadata.json", "size": 1024 * 10},
                ],
            },
            {
                "version": "v1.1.0",
                "version_num": 1,  # DOI: .1001.1 (mismo que v1.0.0)
                "create_fakenodo_version": True,  # Crear con los datos de v1.1.0 (última minor)
                "title": "Weather Patterns Dataset",
                "description": "Updated with 2021 data and improved metadata",
                "days_ago": 45,
                "num_models": "150",
                "num_features": "320",
                "files": [
                    {"name": "weather_data_2020.uvl", "size": 1024 * 500},
                    {"name": "weather_data_2021.uvl", "size": 1024 * 600},
                    {"name": "metadata.json", "size": 1024 * 12},
                ],
            },
            {
                "version": "v2.0.0",
                "version_num": 2,  # DOI: .1001.2 (nueva versión mayor)
                "create_fakenodo_version": True,  # Crear nueva versión mayor
                "title": "Weather Patterns Dataset",
                "description": "Major update: includes 2022 data and new analysis features",
                "days_ago": 7,
                "num_models": "200",
                "num_features": "450",
                "files": [
                    {"name": "weather_data_2020.uvl", "size": 1024 * 500},
                    {"name": "weather_data_2021.uvl", "size": 1024 * 600},
                    {"name": "weather_data_2022.uvl", "size": 1024 * 700},
                    {"name": "analysis_config.uvl", "size": 1024 * 50},
                    {"name": "metadata.json", "size": 1024 * 15},
                ],
            },
        ]

        for idx, ver_data in enumerate(versions_data):
            is_latest = idx == len(versions_data) - 1
            self._create_dataset_version(
                user=user,
                concept=concept,
                deposition_id=deposition_id,
                version_data=ver_data,
                is_latest=is_latest,
                publication_type=PublicationType.CONTINENTAL,
                tags="weather,climate,temperature,patterns",
            )

    def _create_climate_analysis_dataset(self, user):
        """Crea un dataset con 2 versiones en Fakenodo"""

        # 1. Crear concepto de dataset
        concept_doi = "10.1234/fakenodo.concept.1002"
        concept = DataSetConcept(conceptual_doi=concept_doi)
        self.seed([concept])

        # 2. Crear deposition en Fakenodo
        deposition_id = 1002
        deposition = FakenodoDeposition(
            id=deposition_id,
            conceptrecid=str(deposition_id),
            conceptdoi=concept_doi,
            state="published",
            published=True,
            dirty=False,
            doi=f"10.1234/fakenodo.{deposition_id}.1",  # DOI de la última versión (v1.1.0)
            created_at=datetime.now(timezone.utc) - timedelta(days=60),
            updated_at=datetime.now(timezone.utc),
        )
        self.seed([deposition])

        # 3. Crear 2 versiones
        # Nota: v1.0.0 y v1.1.0 comparten el mismo DOI (version_num=1)
        # Solo se crea una entrada en fakenodo_version para la última minor version
        versions_data = [
            {
                "version": "v1.0.0",
                "version_num": 1,  # DOI: .1002.1
                "create_fakenodo_version": False,  # No crear aún
                "title": "Climate Analysis Dataset",
                "description": "Comprehensive climate analysis data for European regions",
                "days_ago": 60,
                "num_models": "75",
                "num_features": "180",
                "files": [
                    {"name": "europe_climate_2019.uvl", "size": 1024 * 400},
                    {"name": "analysis_results.uvl", "size": 1024 * 150},
                ],
            },
            {
                "version": "v1.1.0",
                "version_num": 1,  # DOI: .1002.1 (mismo que v1.0.0)
                "create_fakenodo_version": True,  # Crear con los datos de v1.1.0
                "title": "Climate Analysis Dataset",
                "description": "Updated analysis including 2020 data with refined algorithms",
                "days_ago": 15,
                "num_models": "90",
                "num_features": "220",
                "files": [
                    {"name": "europe_climate_2019.uvl", "size": 1024 * 400},
                    {"name": "europe_climate_2020.uvl", "size": 1024 * 420},
                    {"name": "analysis_results.uvl", "size": 1024 * 180},
                    {"name": "refined_model.uvl", "size": 1024 * 80},
                ],
            },
        ]

        for idx, ver_data in enumerate(versions_data):
            is_latest = idx == len(versions_data) - 1
            self._create_dataset_version(
                user=user,
                concept=concept,
                deposition_id=deposition_id,
                version_data=ver_data,
                is_latest=is_latest,
                publication_type=PublicationType.NATIONAL,
                tags="climate,analysis,europe,temperature",
            )

    def _create_simple_dataset(self, user):
        """Crea un dataset simple con una sola versión"""

        # 1. Crear concepto de dataset
        concept_doi = "10.1234/fakenodo.concept.1003"
        concept = DataSetConcept(conceptual_doi=concept_doi)
        self.seed([concept])

        # 2. Crear deposition en Fakenodo
        deposition_id = 1003
        deposition = FakenodoDeposition(
            id=deposition_id,
            conceptrecid=str(deposition_id),
            conceptdoi=concept_doi,
            state="published",
            published=True,
            dirty=False,
            doi=f"10.1234/fakenodo.{deposition_id}.1",
            created_at=datetime.now(timezone.utc) - timedelta(days=30),
            updated_at=datetime.now(timezone.utc) - timedelta(days=30),
        )
        self.seed([deposition])

        # 3. Crear versión única
        version_data = {
            "version": "v1.0.0",
            "version_num": 1,
            "create_fakenodo_version": True,  # Crear versión en Fakenodo
            "title": "Precipitation Patterns Study",
            "description": "A focused study on precipitation patterns in North America",
            "days_ago": 30,
            "num_models": "50",
            "num_features": "120",
            "files": [
                {"name": "precipitation_data.uvl", "size": 1024 * 300},
                {"name": "stations_info.json", "size": 1024 * 5},
            ],
        }

        self._create_dataset_version(
            user=user,
            concept=concept,
            deposition_id=deposition_id,
            version_data=version_data,
            is_latest=True,
            publication_type=PublicationType.REGIONAL,
            tags="precipitation,weather,north-america",
        )

    def _create_dataset_version(self, user, concept, deposition_id, version_data, is_latest, publication_type, tags):
        """Helper para crear una versión específica de un dataset"""

        version_num = version_data["version_num"]
        version_doi = f"10.1234/fakenodo.{deposition_id}.{version_num}"

        # 1. Crear métricas del dataset
        ds_metrics = DSMetrics(
            number_of_models=version_data["num_models"], number_of_features=version_data["num_features"]
        )
        self.seed([ds_metrics])

        # 2. Crear metadata del dataset
        ds_metadata = DSMetaData(
            deposition_id=deposition_id,
            title=version_data["title"],
            description=version_data["description"],
            publication_type=publication_type,
            publication_doi=None,
            dataset_doi=version_doi,
            tags=tags,
            ds_metrics_id=ds_metrics.id,
        )
        self.seed([ds_metadata])

        # 3. Crear autores
        authors = [
            Author(
                name="Dr. Weather Researcher",
                affiliation="Climate Research Institute",
                orcid="0000-0001-2345-6789",
                ds_meta_data_id=ds_metadata.id,
            ),
            Author(
                name="Prof. Data Scientist",
                affiliation="University of Meteorology",
                orcid="0000-0002-3456-7890",
                ds_meta_data_id=ds_metadata.id,
            ),
        ]
        self.seed(authors)

        # 4. Crear el dataset
        created_at = datetime.now(timezone.utc) - timedelta(days=version_data["days_ago"])
        dataset = DataSet(
            user_id=user.id,
            ds_meta_data_id=ds_metadata.id,
            created_at=created_at,
            ds_concept_id=concept.id,
            version_number=version_data["version"],
            is_latest=is_latest,
        )
        self.seed([dataset])

        # 5. Crear feature models y archivos
        self._create_feature_models_and_files(dataset, version_data["files"], publication_type)

        # 6. Crear versión en Fakenodo solo si es necesario (última minor o nueva major)
        if version_data.get("create_fakenodo_version", True):
            self._create_fakenodo_version(deposition_id, version_num, version_doi, ds_metadata, version_data["files"])

        print(f"   ✓ Created {version_data['title']} {version_data['version']}")

    def _create_feature_models_and_files(self, dataset, files_data, publication_type):
        """Crea feature models y archivos para un dataset"""

        # Crear un feature model por archivo principal
        for file_data in files_data:
            # Crear métricas del FM
            fm_metrics = FMMetrics(solver="SAT4J", not_solver="N/A")
            self.seed([fm_metrics])

            # Crear metadata del FM
            fm_metadata = FMMetaData(
                filename=file_data["name"],
                title=file_data["name"].replace(".uvl", "").replace("_", " ").title(),
                description=f"Feature model for {file_data['name']}",
                publication_type=publication_type,
                publication_doi=None,
                tags="feature-model,weather-data",
                version="1.0",
                fm_metrics_id=fm_metrics.id,
            )
            self.seed([fm_metadata])

            # Crear feature model
            feature_model = FeatureModel(data_set_id=dataset.id, fm_meta_data_id=fm_metadata.id)
            self.seed([feature_model])

            # Crear archivo (Hubfile)
            hubfile = Hubfile(
                name=file_data["name"],
                checksum=self._generate_checksum(file_data["name"]),
                size=file_data["size"],
                feature_model_id=feature_model.id,
            )
            self.seed([hubfile])

    def _create_fakenodo_version(self, deposition_id, version_num, version_doi, ds_metadata, files_data):
        """Crea una versión en Fakenodo"""

        # Preparar metadata JSON
        metadata = {
            "title": ds_metadata.title,
            "description": ds_metadata.description,
            "publication_type": ds_metadata.publication_type.value,
            "doi": version_doi,
            "version": version_num,
        }

        # Preparar files JSON
        files_json = []
        for file_data in files_data:
            file_id = str(uuid.uuid4())
            files_json.append(
                {
                    "id": file_id,
                    "name": file_data["name"],
                    "size": file_data["size"],
                    "checksum": self._generate_checksum(file_data["name"]),
                }
            )

            # Crear FakenodoFile
            fakenodo_file = FakenodoFile(
                file_id=file_id,
                deposition_id=deposition_id,
                name=file_data["name"],
                size=file_data["size"],
                created_at=datetime.now(timezone.utc),
            )
            self.seed([fakenodo_file])

        # Crear versión de Fakenodo
        fakenodo_version = FakenodoVersion(
            deposition_id=deposition_id,
            version=version_num,
            doi=version_doi,
            metadata_json=json.dumps(metadata),
            files_json=json.dumps(files_json),
            created_at=datetime.now(timezone.utc),
        )
        self.seed([fakenodo_version])

    def _generate_checksum(self, filename):
        """Genera un checksum simulado para un archivo"""
        import hashlib

        return hashlib.md5(f"{filename}-{datetime.now().timestamp()}".encode()).hexdigest()
