#!/usr/bin/env python
"""
Script para limpiar completamente los datasets y resetear los AUTO_INCREMENT.
Uso: python scripts/reset_datasets.py
"""

import os
import shutil
import sys

# Add parent directory to path to import app modules  # noqa: E402
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app, db  # noqa: E402
from app.modules.dataset.models import Author, DataSet, DSMetaData, DSMetrics, DSViewRecord  # noqa: E402
from app.modules.fakenodo.models import FakenodoDeposition, FakenodoFile, FakenodoVersion  # noqa: E402
from app.modules.featuremodel.models import FeatureModel, FMMetaData  # noqa: E402
from app.modules.hubfile.models import Hubfile  # noqa: E402


def reset_datasets():
    """Limpia todos los datasets y resetea AUTO_INCREMENT."""
    app = create_app()

    with app.app_context():
        print("=" * 70)
        print("LIMPIEZA COMPLETA DE DATASETS + RESET AUTO_INCREMENT")
        print("=" * 70)

        # Eliminar todos los datos en orden correcto (respetando foreign keys)
        print("\n Eliminando datos...")
        Hubfile.query.delete()
        FeatureModel.query.delete()
        FMMetaData.query.delete()
        DSViewRecord.query.delete()
        DataSet.query.delete()
        Author.query.delete()
        DSMetaData.query.delete()
        DSMetrics.query.delete()
        FakenodoFile.query.delete()
        FakenodoVersion.query.delete()
        FakenodoDeposition.query.delete()
        db.session.commit()
        print(" Datos eliminados")

        # Resetear AUTO_INCREMENT
        print("\nReseteando AUTO_INCREMENT...")
        tables_to_reset = [
            "data_set",
            "ds_meta_data",
            "ds_metrics",
            "author",
            "ds_view_record",
            "feature_model",
            "fm_meta_data",
            "file",  # hubfile table
            "fakenodo_deposition",
            "fakenodo_version",
            "fakenodo_file",
        ]

        for table in tables_to_reset:
            try:
                db.session.execute(db.text(f"ALTER TABLE {table} AUTO_INCREMENT = 1"))
                print(f"  ✓ {table}")
            except Exception as e:
                print(f"  ✗ {table}: {e}")

        db.session.commit()

        # Limpiar carpetas físicas
        print("\n📁 Limpiando carpetas de archivos...")
        deleted_folders = 0
        uploads_dir = "uploads"
        if os.path.exists(uploads_dir):
            for item in os.listdir(uploads_dir):
                item_path = os.path.join(uploads_dir, item)
                if item.startswith("user_") and os.path.isdir(item_path):
                    for dataset_folder in os.listdir(item_path):
                        if dataset_folder.startswith("dataset_"):
                            shutil.rmtree(os.path.join(item_path, dataset_folder))
                            deleted_folders += 1

        if deleted_folders > 0:
            print(f"  ✓ {deleted_folders} carpetas eliminadas")
        else:
            print("  No había carpetas de datasets")

        # Limpiar temp
        temp_dir = "uploads/temp"
        deleted_temp = 0
        if os.path.exists(temp_dir):
            for user_folder in os.listdir(temp_dir):
                user_path = os.path.join(temp_dir, user_folder)
                if os.path.isdir(user_path):
                    shutil.rmtree(user_path)
                    deleted_temp += 1

        if deleted_temp > 0:
            print(f"  ✓ {deleted_temp} carpetas temp eliminadas")

        # Verificar AUTO_INCREMENT después del reset
        print("\n Verificando AUTO_INCREMENT...")
        check_tables = ["data_set", "ds_meta_data", "fakenodo_deposition"]
        for table in check_tables:
            result = db.session.execute(db.text(f"SHOW TABLE STATUS LIKE '{table}'")).fetchone()
            if result:
                auto_inc = result[10]
                print(f"  • {table}: {auto_inc}")

        print("\n" + "=" * 70)
        print(" RESET COMPLETADO")
        print("=" * 70)
        print("\nPróximo dataset creado tendrá:")
        print("  • dataset.id = 1")
        print("  • deposition_id = 1")
        print("  • DOI v1: 10.1234/fakenodo.1.v1")
        print("\nAl republicar (versión 2):")
        print("  • dataset.id = 2 (nuevo dataset independiente)")
        print("  • deposition_id = 1 (mismo concepto base)")
        print("  • DOI v2: 10.1234/fakenodo.1.v2")
        print("=" * 70)


if __name__ == "__main__":
    print("\n ADVERTENCIA: Este script eliminará TODOS los datasets y sus archivos.")
    response = input("¿Estás seguro? (escribe 'SI' para continuar): ")

    if response == "SI":
        reset_datasets()
    else:
        print("Operación cancelada")
