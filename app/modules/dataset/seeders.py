import csv
import os
from datetime import datetime, timezone

from dotenv import load_dotenv

from app.modules.auth.models import User
from app.modules.dataset.models import Author, DataSet, DSMetaData, DSMetrics, PublicationType
from app.modules.dataset.validator import REQUIRED_COLUMNS
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

        # Create DSMetaData instances (ahora 6 datasets para poder distribuir 12 CSV -> 2 CSV por dataset)
        ds_meta_data_list = [
            DSMetaData(
                deposition_id=1 + i,
                title=f"Sample dataset {i+1}",
                description=f"Description for dataset {i+1}",
                publication_type=PublicationType.NONE.name,
                publication_doi=f"10.1234/dataset{i+1}",
                dataset_doi=f"10.1234/dataset{i+1}",
                tags="tag1, tag2",
                ds_metrics_id=seeded_ds_metrics.id,
            )
            for i in range(6)  # 6 datasets
        ]
        seeded_ds_meta_data = self.seed(ds_meta_data_list)

        # Create Author instances and associate with DSMetaData
        authors = [
            Author(
                name=f"Author {i+1}",
                affiliation=f"Affiliation {i+1}",
                orcid=f"0000-0000-0000-000{i}",
                ds_meta_data_id=seeded_ds_meta_data[i % 6].id,
            )
            for i in range(6)
        ]
        self.seed(authors)

        # Create DataSet instances (6 datasets)
        datasets = [
            DataSet(
                user_id=user1.id if i % 2 == 0 else user2.id,
                ds_meta_data_id=seeded_ds_meta_data[i].id,
                created_at=datetime.now(timezone.utc),
            )
            for i in range(6)
        ]
        seeded_datasets = self.seed(datasets)

        # For each dataset create one CSV and one README (md)
        fm_meta_data_list = []
        for i in range(len(seeded_datasets)):
            fm_meta_data_list.append(
                FMMetaData(
                    filename=f"dataset_{i+1}.csv",
                    title=f"Dataset file {i+1}",
                    description=f"CSV data file for dataset {i+1}",
                    publication_type=PublicationType.NONE.name,
                    publication_doi=f"10.1234/fm{i+1}",
                    tags="tag1, tag2",
                    version="1.0",
                )
            )

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
        # Si querías copiar plantillas, podrías usar src_folder; aquí generamos CSVs dinámicamente.
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
