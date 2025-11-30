import csv
import os
from datetime import datetime, timezone

from dotenv import load_dotenv

from app.modules.auth.models import User

# 1. AÑADIR DataSetConcept AL IMPORT
from app.modules.dataset.models import Author, DataSet, DataSetConcept, DSMetaData, DSMetrics, PublicationType
from app.modules.featuremodel.models import FeatureModel, FMMetaData
from app.modules.hubfile.models import Hubfile
from core.seeders.BaseSeeder import BaseSeeder

# Si tienes REQUIRED_COLUMNS definido centralmente, también podrías importarlo.
REQUIRED_COLUMNS = [
    "_temp_mean",
    "_temp_max",
    "_temp_min",
    "_cloud_cover",
    "_global_radiation",
    "_humidity",
    "_pressure",
    "_precipitation",
    "_sunshine",
    "_wind_gust",
    "_wind_speed",
]


class DataSetSeeder(BaseSeeder):

    priority = 2  # Lower priority

    def run(self):
        # Retrieve users
        user1 = User.query.filter_by(email="user1@example.com").first()
        user2 = User.query.filter_by(email="user2@example.com").first()

        if not user1 or not user2:
            raise Exception("Users not found. Please seed users first.")

        # Create DSMetrics instance
        ds_metrics = DSMetrics(number_of_models="5", number_of_features="50")
        seeded_ds_metrics = self.seed([ds_metrics])[0]

        # === START OF CHANGES ===

        # 1. Crear DataSetConcept (Padres)
        # Crearemos 3 conceptos para agrupar los 6 datasets
        concepts_to_seed = [
            DataSetConcept(conceptual_doi="10.seed/concept.1"),
            DataSetConcept(conceptual_doi="10.seed/concept.2"),
            DataSetConcept(conceptual_doi="10.seed/concept.3"),
        ]
        seeded_concepts = self.seed(concepts_to_seed)

        # 2. Crear DSMetaData instances (6 total, 2 versiones por concepto)
        ds_meta_data_list = [
            # Concepto 1, Versión 1
            DSMetaData(
                deposition_id=1001,
                title="Weather Data (V1)",
                description="Description for dataset 1, version 1",
                publication_type=PublicationType.DATA_MANAGEMENT_PLAN,
                publication_doi="10.1234/paper.1",
                dataset_doi="10.seed/v1.1",  # <-- DOI Específico V1
                tags="tag1, tag2",
                ds_metrics_id=seeded_ds_metrics.id,
            ),
            # Concepto 1, Versión 2
            DSMetaData(
                deposition_id=1002,
                title="Weather Data (V2)",
                description="Description for dataset 1, version 2",
                publication_type=PublicationType.DATA_MANAGEMENT_PLAN,
                publication_doi="10.1234/paper.1",
                dataset_doi="10.seed/v1.2",  # <-- DOI Específico V2
                tags="tag1, tag2, updated",
                ds_metrics_id=seeded_ds_metrics.id,
            ),
            # Concepto 2, Versión 1
            DSMetaData(
                deposition_id=1003,
                title="UVL Models (V1)",
                description="Description for dataset 2, version 1",
                publication_type=PublicationType.OTHER,
                publication_doi="10.1234/paper.2",
                dataset_doi="10.seed/v2.1",  # <-- DOI Específico
                tags="uvl, models",
                ds_metrics_id=seeded_ds_metrics.id,
            ),
            # Concepto 2, Versión 2
            DSMetaData(
                deposition_id=1004,
                title="UVL Models (V2 - expanded)",
                description="Description for dataset 2, version 2",
                publication_type=PublicationType.OTHER,
                publication_doi="10.1234/paper.2",
                dataset_doi="10.seed/v2.2",  # <-- DOI Específico
                tags="uvl, models, expanded",
                ds_metrics_id=seeded_ds_metrics.id,
            ),
            # Concepto 3, Versión 1
            DSMetaData(
                deposition_id=1005,
                title="Empty Dataset (V1)",
                description="Description for dataset 3, version 1",
                publication_type=PublicationType.REPORT,
                publication_doi="10.1234/paper.3",
                dataset_doi="10.seed/v3.1",  # <-- DOI Específico
                tags="empty",
                ds_metrics_id=seeded_ds_metrics.id,
            ),
            # Concepto 3, Versión 2
            DSMetaData(
                deposition_id=1006,
                title="Empty Dataset (V2 - metadata edit)",
                description="Description for dataset 3, version 2",
                publication_type=PublicationType.REPORT,
                publication_doi="10.1234/paper.3",
                dataset_doi="10.seed/v3.2",  # <-- DOI Específico
                tags="empty, metadata",
                ds_metrics_id=seeded_ds_metrics.id,
            ),
        ]
        seeded_ds_meta_data = self.seed(ds_meta_data_list)

        # 3. Crear Author instances (esta lógica es correcta, 1 autor por metadato)
        authors = [
            Author(
                name=f"Author {i+1}",
                affiliation=f"Affiliation {i+1}",
                orcid=f"0000-0000-0000-000{i}",
                ds_meta_data_id=seeded_ds_meta_data[i].id,
            )
            for i in range(6)
        ]
        self.seed(authors)

        # 4. Crear DataSet instances (enlazados a los padres/conceptos)
        datasets = [
            # Concepto 1, V1 (user1)
            DataSet(
                user_id=user1.id,
                ds_meta_data_id=seeded_ds_meta_data[0].id,
                created_at=datetime(2023, 1, 1, tzinfo=timezone.utc),  # Fecha antigua
                ds_concept_id=seeded_concepts[0].id,  # <-- Enlace al Padre 1
                version_number="v1.0.0",
                is_latest=False,  # No es la última
            ),
            # Concepto 1, V2 (user1)
            DataSet(
                user_id=user1.id,
                ds_meta_data_id=seeded_ds_meta_data[1].id,
                created_at=datetime(2023, 1, 2, tzinfo=timezone.utc),  # Fecha nueva
                ds_concept_id=seeded_concepts[0].id,  # <-- Enlace al Padre 1
                version_number="v2.0.0",
                is_latest=True,  # Es la última
            ),
            # Concepto 2, V1 (user2)
            DataSet(
                user_id=user2.id,
                ds_meta_data_id=seeded_ds_meta_data[2].id,
                created_at=datetime(2023, 2, 1, tzinfo=timezone.utc),
                ds_concept_id=seeded_concepts[1].id,  # <-- Enlace al Padre 2
                version_number="v1.0.0",
                is_latest=False,
            ),
            # Concepto 2, V2 (user2)
            DataSet(
                user_id=user2.id,
                ds_meta_data_id=seeded_ds_meta_data[3].id,
                created_at=datetime(2023, 2, 2, tzinfo=timezone.utc),
                ds_concept_id=seeded_concepts[1].id,  # <-- Enlace al Padre 2
                version_number="v2.0.0",
                is_latest=True,
            ),
            # Concepto 3, V1 (user1)
            DataSet(
                user_id=user1.id,
                ds_meta_data_id=seeded_ds_meta_data[4].id,
                created_at=datetime(2023, 3, 1, tzinfo=timezone.utc),
                ds_concept_id=seeded_concepts[2].id,  # <-- Enlace al Padre 3
                version_number="v1.0.0",
                is_latest=False,
            ),
            # Concepto 3, V2 (user1)
            DataSet(
                user_id=user1.id,
                ds_meta_data_id=seeded_ds_meta_data[5].id,
                created_at=datetime(2023, 3, 2, tzinfo=timezone.utc),
                ds_concept_id=seeded_concepts[2].id,  # <-- Enlace al Padre 3
                version_number="v1.1.0",  # Ejemplo de versión menor
                is_latest=True,
            ),
        ]
        seeded_datasets = self.seed(datasets)

        # === END OF CHANGES ===

        # Create 12 FMMetaData instances
        fm_meta_data_list = [
            FMMetaData(
                filename=f"file{i+1}.csv",
                title=f"Feature Model {i+1}",
                description=f"Description for feature model {i+1}",
                publication_type=PublicationType.OTHER,
                publication_doi=f"10.1234/fm{i+1}",
                tags="tag1, tag2",
                version="1.0",
            )
            for i in range(12)
        ]
        seeded_fm_meta_data = self.seed(fm_meta_data_list)

        # Create Author instances and associate with FMMetaData
        fm_authors = [
            Author(
                name=f"Author {i+7}",
                affiliation=f"Affiliation {i+7}",
                orcid=f"0000-0000-0000-00{i+7}",
                fm_meta_data_id=seeded_fm_meta_data[i].id,
            )
            for i in range(12)
        ]
        self.seed(fm_authors)

        # Create 12 FeatureModel instances, asignando 2 por dataset (para no superar max_csv=2 por paquete)
        # ESTA LÓGICA (i // 2) SIGUE FUNCIONANDO PERFECTAMENTE
        feature_models = [
            FeatureModel(
                # 2 FMs por dataset
                data_set_id=seeded_datasets[i // 2].id,
                fm_meta_data_id=seeded_fm_meta_data[i].id,
            )
            for i in range(12)
        ]
        seeded_feature_models = self.seed(feature_models)

        # Create CSV + README files, associate them with FeatureModels and create Hubfile entries
        load_dotenv()
        working_dir = os.getenv("WORKING_DIR", "")
        # ESTA LÓGICA SIGUE FUNCIONANDO PERFECTAMENTE
        for i in range(12):
            csv_name = f"file{i+1}.csv"
            readme_name = f"readme{i+1}.txt"

            feature_model = seeded_feature_models[i]
            dataset = next(ds for ds in seeded_datasets if ds.id == feature_model.data_set_id)
            user_id = dataset.user_id

            dest_folder = os.path.join(working_dir, "uploads", f"user_{user_id}", f"dataset_{dataset.id}")
            os.makedirs(dest_folder, exist_ok=True)

            # Crear CSV: incluir DATE + todas las columnas requeridas para asegurar que el validador pase.
            csv_path = os.path.join(dest_folder, csv_name)
            with open(csv_path, "w", encoding="utf-8", newline="") as csvfile:
                writer = csv.writer(csvfile, delimiter=",")
                headers = ["DATE"] + REQUIRED_COLUMNS
                writer.writerow(headers)
                # Una fila de ejemplo (DATE + ceros)
                example_row = ["2020-01-01"] + ["0"] * len(REQUIRED_COLUMNS)
                writer.writerow(example_row)

            # Crear README mínimo
            readme_path = os.path.join(dest_folder, readme_name)
            with open(readme_path, "w", encoding="utf-8") as fh:
                fh.write(f"Readme for {csv_name}\n")
                fh.write("This is a generated README for seeding purposes.\n")

            # Crear Hubfile para CSV
            csv_size = os.path.getsize(csv_path)
            csv_hf = Hubfile(
                name=csv_name,
                checksum=f"csv_checksum_{i+1}",
                size=csv_size,
                feature_model_id=feature_model.id,
            )

            # Crear Hubfile para README
            readme_size = os.path.getsize(readme_path)
            readme_hf = Hubfile(
                name=readme_name,
                checksum=f"readme_checksum_{i+1}",
                size=readme_size,
                feature_model_id=feature_model.id,
            )

            # Guardar ambos Hubfiles
            self.seed([csv_hf, readme_hf])
