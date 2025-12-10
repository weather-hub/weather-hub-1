import os
from datetime import datetime, timezone

from dotenv import load_dotenv

from app import db
from app.modules.auth.models import User
from app.modules.dataset.models import Author, DataSet, DataSetConcept, DSMetaData, DSMetrics, PublicationType
from app.modules.featuremodel.models import FeatureModel, FMMetaData
from app.modules.hubfile.models import Hubfile
from core.seeders.BaseSeeder import BaseSeeder

# Columnas necesarias para el CSV
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
    priority = 2

    def run(self):
        print("--> [DataSetSeeder] Ejecutando versión AMPLIADA Y CORREGIDA...")

        # -----------------------------------------------------------------------
        # 1. USUARIOS
        # -----------------------------------------------------------------------
        user1 = User.query.filter_by(email="user1@example.com").first()
        user2 = User.query.filter_by(email="user2@example.com").first()
        if not user1:
            user1 = User(email="user1@example.com", password="password", is_admin=False)
            db.session.add(user1)
        if not user2:
            user2 = User(email="user2@example.com", password="password", is_admin=False)
            db.session.add(user2)
        db.session.commit()

        # -----------------------------------------------------------------------
        # 2. MÉTRICAS
        # -----------------------------------------------------------------------
        ds_metrics = DSMetrics(number_of_models="5", number_of_features="50")
        db.session.add(ds_metrics)
        db.session.commit()

        # -----------------------------------------------------------------------
        # 3. CONCEPTOS (PADRES)
        # -----------------------------------------------------------------------
        print("--> Creando Conceptos...")
        concepts = [
            DataSetConcept(conceptual_doi="10.seed/concept.1"),
            DataSetConcept(conceptual_doi="10.seed/concept.2"),
            DataSetConcept(conceptual_doi="10.seed/concept.3"),
            # Añadimos uno más
            DataSetConcept(conceptual_doi="10.seed/concept.4"),
        ]
        db.session.add_all(concepts)
        db.session.commit()

        # Mapeamos DOI -> ID para usarlos al crear los hijos
        c_map = {c.conceptual_doi: c.id for c in concepts}

        # -----------------------------------------------------------------------
        # 4. DATASETS
        # -----------------------------------------------------------------------
        print("--> Creando Datasets vinculados...")

        # Estructura: (Concept DOI, User, [(Version, Title)])
        data = [
            # Concepto 1: Historia completa de versiones
            (
                "10.seed/concept.1",
                user1,
                [
                    ("v1.0.0", "Weather Data V1"),
                    ("v1.1.0", "Weather Data V1.1 (Fixes)"),
                    ("v2.0.0", "Weather Data V2 (Major)"),
                ],
            ),
            # Concepto 2: Otro usuario
            ("10.seed/concept.2", user2, [("v1.0.0", "UVL Models V1")]),
            # Concepto 3: Dataset vacío o simple
            ("10.seed/concept.3", user1, [("v1.0.0", "Empty Set V1")]),
            # Concepto 4: Nuevo dato
            ("10.seed/concept.4", user2, [("v1.0.0", "Experimental Data"), ("v1.0.1", "Experimental Data (Patch)")]),
        ]

        created_ds_ids = []
        counter = 0

        for c_doi, user, versions in data:
            parent_id = c_map.get(c_doi)

            for idx, (ver, title) in enumerate(versions):
                counter += 1

                # A. Metadato
                meta = DSMetaData(
                    deposition_id=5000 + counter,
                    title=title,
                    description=f"Auto-generated description for {title}. This dataset contains sample data.",
                    publication_type=PublicationType.NATIONAL,
                    publication_doi=f"http://doi.org/p/{counter}",
                    dataset_doi=f"{c_doi}.{ver}",
                    tags="tag1, tag2, seed",
                    ds_metrics_id=ds_metrics.id,
                )
                db.session.add(meta)
                db.session.flush()

                # B. Dataset (Con el enlace al PADRE arreglado)
                ds = DataSet(
                    user_id=user.id,
                    ds_meta_data_id=meta.id,
                    ds_concept_id=parent_id,  # <--- Importante
                    created_at=datetime.now(timezone.utc),
                    version_number=ver,
                    is_latest=(idx == len(versions) - 1),
                )
                db.session.add(ds)
                db.session.flush()
                created_ds_ids.append(ds.id)

                # C. Autor
                db.session.add(
                    Author(
                        name=f"Author {counter}",
                        affiliation="University of Seeding",
                        orcid="0000-0000-0000-0000",
                        ds_meta_data_id=meta.id,
                    )
                )

        db.session.commit()

        # -----------------------------------------------------------------------
        # 5. ARCHIVOS FÍSICOS Y MODELOS
        # -----------------------------------------------------------------------
        print("--> Generando archivos físicos (2 por dataset)...")
        load_dotenv()
        wd = os.getenv("WORKING_DIR", "app")

        for ds_id in created_ds_ids:
            ds = DataSet.query.get(ds_id)

            # Vamos a crear 2 archivos por cada dataset para tener más volumen
            for i in range(1, 3):
                filename = f"model_{ds.id}_{i}.csv"

                # A. Feature Model Metadata (AQUÍ ESTABA EL ERROR ANTES)
                fm_meta = FMMetaData(
                    filename=filename,
                    title=f"Feature Model {i} for DS {ds.id}",
                    # <--- AÑADIDO (Esto arregla el error 1048)
                    description=f"Description for feature model {i} in dataset {ds.id}",
                    publication_type=PublicationType.OTHER,
                    # <--- AÑADIDO
                    publication_doi=f"http://doi.org/fm/{ds.id}/{i}",
                    tags="auto, generated",  # <--- AÑADIDO
                    version="1.0",
                )
                db.session.add(fm_meta)
                db.session.flush()

                # B. Feature Model
                fm = FeatureModel(data_set_id=ds.id, fm_meta_data_id=fm_meta.id)
                db.session.add(fm)
                db.session.flush()

                # C. Archivo Físico
                path = os.path.join(wd, "uploads", f"user_{ds.user_id}", f"dataset_{ds.id}")
                os.makedirs(path, exist_ok=True)

                full_path = os.path.join(path, filename)
                with open(full_path, "w") as f:
                    f.write("DATE," + ",".join(REQUIRED_COLUMNS) + "\n")
                    f.write("2023-01-01," + ",".join(["0"] * len(REQUIRED_COLUMNS)))

                # D. Hubfile
                db.session.add(Hubfile(name=filename, checksum=f"chk_{ds.id}_{i}", size=100, feature_model_id=fm.id))

        db.session.commit()
        print("--> ¡Seeder completado correctamente!")
