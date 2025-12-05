import csv
import os
from datetime import datetime, timedelta, timezone

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
        concepts_to_seed = [
            DataSetConcept(conceptual_doi="10.seed/concept.1"),
            DataSetConcept(conceptual_doi="10.seed/concept.2"),
            DataSetConcept(conceptual_doi="10.seed/concept.3"),
        ]
        seeded_concepts = self.seed(concepts_to_seed)

        # 2. Definir estructura con versiones por concepto
        datasets_structure = [
            (
                "10.seed/concept.1",
                user1,
                [
                    ("v1.0.0", "Weather Data (V1)", "Description for dataset 1, version 1", "tag1, tag2", 0),
                    ("v1.1.0", "Weather Data (V1.1)", "Minor fixes", "tag1, tag2, fixes", 1),
                    ("v2.0.0", "Weather Data (V2)", "Major update", "tag1, tag2, major", 2),
                ],
            ),
            (
                "10.seed/concept.2",
                user2,
                [
                    ("v1.0.0", "UVL Models (V1)", "Initial release", "uvl, models", 31),
                    ("v2.0.0", "UVL Models (V2 - expanded)", "Major expansion", "uvl, models, expanded", 32),
                ],
            ),
            (
                "10.seed/concept.3",
                user1,
                [
                    ("v1.0.0", "Empty Dataset (V1)", "Description for dataset 3, version 1", "empty", 60),
                    ("v1.1.0", "Empty Dataset (V1.1 - metadata edit)", "Minor metadata edit", "empty, metadata", 61),
                ],
            ),
        ]

        ds_meta_data_list = []
        datasets = []
        authors = []

        # Mapa: para cada concepto, un DOI específico por major (minor/patch comparten)
        specific_doi_by_concept_and_major = {}

        base_date = datetime(2023, 1, 1, tzinfo=timezone.utc)

        for concept_doi, owner_user, versions in datasets_structure:
            for idx, (version, title, description, tags, days_offset) in enumerate(versions):
                # extraer major
                major = str(version).lstrip("v").split(".")[0]
                key = (concept_doi, major)
                if key not in specific_doi_by_concept_and_major:
                    # nuevo DOI específico para este major
                    specific_doi_by_concept_and_major[key] = f"{concept_doi}.v{major}"

                dataset_doi = specific_doi_by_concept_and_major[key]

                ds_meta = DSMetaData(
                    deposition_id=1000 + len(ds_meta_data_list) + 1,
                    title=title,
                    description=description,
                    publication_type=PublicationType.NATIONAL,
                    publication_doi=f"https://doi.org/10.1234/paper.{len(ds_meta_data_list)+1}",
                    dataset_doi=dataset_doi,
                    tags=tags,
                    ds_metrics_id=seeded_ds_metrics.id,
                )
                ds_meta_data_list.append(ds_meta)

                # autor simple para cada metadato
                authors.append(
                    Author(
                        name=f"Author {len(ds_meta_data_list)}",
                        affiliation=f"Affiliation {len(ds_meta_data_list)}",
                        orcid=f"0000-0000-0000-{str(len(ds_meta_data_list)).zfill(4)}",
                        # fm_meta_data_id se asigna después para FMs, aquí usamos ds_meta
                        ds_meta_data_id=None,  # se rellenará tras seed de metadatos
                    )
                )

                datasets.append(
                    DataSet(
                        user_id=owner_user.id,
                        ds_meta_data_id=None,  # se rellena tras seed
                        created_at=base_date.replace(tzinfo=timezone.utc) + timedelta(days=days_offset),
                        ds_concept_id=None,  # se rellena tras seed
                        version_number=version,
                        is_latest=(idx == len(versions) - 1),
                    )
                )

        seeded_ds_meta_data = self.seed(ds_meta_data_list)

        # asignar ds_meta_data_id a autores
        for i, author in enumerate(authors):
            author.ds_meta_data_id = seeded_ds_meta_data[i].id
        self.seed(authors)

        # asociar datasets con conceptos y metadatos en el mismo orden
        seeded_datasets = []
        meta_idx = 0
        concept_idx = 0
        for concept_idx, (_, _, versions) in enumerate(datasets_structure):
            for _ in versions:
                ds = datasets[meta_idx]
                ds.ds_meta_data_id = seeded_ds_meta_data[meta_idx].id
                ds.ds_concept_id = seeded_concepts[concept_idx].id
                seeded_datasets.append(ds)
                meta_idx += 1
        seeded_datasets = self.seed(seeded_datasets)
        # === END OF CHANGES ===

        # Create FMMetaData, Authors y FeatureModels (DOI válido)
        fm_meta_data_list = [
            FMMetaData(
                filename=f"file{i+1}.csv",
                title=f"Feature Model {i+1}",
                description=f"Description for feature model {i+1}",
                publication_type=PublicationType.OTHER,
                publication_doi=f"https://doi.org/10.1234/fm.{i+1}",
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
