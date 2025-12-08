import csv

import pytest

from app.modules.dataset.validator import REQUIRED_COLUMNS, validate_dataset_package

# Fixture para crear estructura básica


@pytest.fixture
def base_dataset_structure(tmp_path):
    d = tmp_path / "dataset"
    d.mkdir()
    readme = d / "README.md"
    readme.write_text("Dataset description")
    return d, readme


def create_csv(path, headers, rows, encoding="utf-8", delimiter=","):
    """Helper para crear CSVs con control total sobre formato y encoding"""
    with open(path, "w", newline="", encoding=encoding) as f:
        # Si es delimiter normal, usamos csv.writer
        if delimiter == ",":
            writer = csv.writer(f)
            writer.writerow(headers)
            for r in rows:
                writer.writerow(r)
        else:
            # Forzamos formato manual para probar el Sniffer
            header_line = delimiter.join(headers)
            f.write(header_line + "\n")
            for r in rows:
                f.write(delimiter.join(r) + "\n")


# --- BLOQUE 1: Estructura y Cantidad de Ficheros ---


def test_validate_fail_no_csv(base_dataset_structure):
    d, readme = base_dataset_structure
    # Solo README, sin CSV
    with pytest.raises(ValueError, match="No se subió ningún CSV"):
        validate_dataset_package([str(readme)], REQUIRED_COLUMNS)


def test_validate_fail_too_many_csvs(base_dataset_structure):
    d, readme = base_dataset_structure
    # Creamos 3 CSVs (el límite por defecto es 2)
    csvs = []
    for i in range(3):
        p = d / f"file{i}.csv"
        create_csv(p, ["DATE"] + REQUIRED_COLUMNS, [["2023-01-01"] + ["0"] * 11])
        csvs.append(str(p))

    with pytest.raises(ValueError, match="Máximo 2 CSV permitidos"):
        validate_dataset_package(csvs + [str(readme)], REQUIRED_COLUMNS)


def test_validate_fail_no_readme(base_dataset_structure):
    d, _ = base_dataset_structure
    csv_file = d / "data.csv"
    create_csv(csv_file, ["DATE"] + REQUIRED_COLUMNS, [["2023-01-01"] + ["0"] * 11])

    # Pasamos require_readme=True
    with pytest.raises(ValueError, match="Falta README"):
        validate_dataset_package([str(csv_file)], REQUIRED_COLUMNS, require_readme=True)


# --- BLOQUE 2: Formatos de CSV (Delimitadores y Encoding) ---


def test_validate_semicolon_delimiter(base_dataset_structure):
    """Prueba que csv.Sniffer detecta punto y coma (común en Excel europeo)"""
    d, readme = base_dataset_structure
    csv_file = d / "semicolon.csv"

    # Crear CSV separado por ;
    create_csv(csv_file, ["DATE"] + REQUIRED_COLUMNS, [["2023-01-01"] + ["0"] * 11], delimiter=";")

    # Debería pasar sin errores si el Sniffer funciona
    validate_dataset_package([str(csv_file), str(readme)], REQUIRED_COLUMNS)


def test_validate_latin1_encoding(base_dataset_structure):
    """Prueba el fallback a latin-1 cuando utf-8 falla"""
    d, readme = base_dataset_structure
    csv_file = d / "latin1.csv"

    # Usamos un carácter que rompe UTF-8 si se lee mal (ej: tilde o ñ) en una cabecera extra
    headers = ["DATE", "AÑO"] + REQUIRED_COLUMNS
    rows = [["2023", "2023"] + ["0"] * 11]

    create_csv(csv_file, headers, rows, encoding="latin-1")

    # El validador debería capturar la excepción UnicodeDecodeError y reintentar con latin-1
    validate_dataset_package([str(csv_file), str(readme)], REQUIRED_COLUMNS)


# --- BLOQUE 3: Matching de Cabeceras (Fuzzy Logic) ---


@pytest.mark.parametrize(
    "prefix, suffix",
    [
        ("", ""),  # Exacto: _temp_mean
        ("Station", ""),  # Prefijo sin guión: Station_temp_mean (vía 'in')
        ("Station_", ""),  # Prefijo con guión: Station__temp_mean (vía lógica custom)
        ("", "_Sensor"),  # Sufijo: _temp_mean_Sensor (vía 'in')
        ("Basel_", ""),  # Caso real: Basel__temp_mean
    ],
)
def test_fuzzy_header_variations(base_dataset_structure, prefix, suffix):
    d, readme = base_dataset_structure
    csv_file = d / "fuzzy.csv"

    # Construimos cabeceras dinámicas: Prefijo + Columna + Sufijo
    # Ej: "Station_temp_mean"
    headers = ["DATE"]
    for col in REQUIRED_COLUMNS:
        # Limpiamos guiones bajos extra si se generan al concatenar
        clean_col = col
        h = f"{prefix}{clean_col}{suffix}"
        headers.append(h)

    create_csv(csv_file, headers, [["2025-01-01"] + ["0"] * 11])

    # Debe pasar
    validate_dataset_package([str(csv_file), str(readme)], REQUIRED_COLUMNS)


def test_validate_headers_case_insensitive(base_dataset_structure):
    d, readme = base_dataset_structure
    csv_file = d / "caps.csv"

    # Convertimos todo a MAYÚSCULAS: _TEMP_MEAN
    headers = ["date"] + [c.upper() for c in REQUIRED_COLUMNS]
    create_csv(csv_file, headers, [["2023"] + ["0"] * 11])

    validate_dataset_package([str(csv_file), str(readme)], REQUIRED_COLUMNS)


# --- BLOQUE 4: Columnas Faltantes ---


def test_validate_missing_columns_logic(base_dataset_structure):
    d, readme = base_dataset_structure
    csv_file = d / "incomplete.csv"

    # Quitamos DOS columnas para ver si el error las lista
    missing = [REQUIRED_COLUMNS[0], REQUIRED_COLUMNS[-1]]
    present = REQUIRED_COLUMNS[1:-1]

    create_csv(csv_file, ["DATE"] + present, [["2023"] + ["0"] * len(present)])

    with pytest.raises(ValueError) as excinfo:
        validate_dataset_package([str(csv_file), str(readme)], REQUIRED_COLUMNS)

    # Verificamos que el mensaje de error mencione explícitamente qué falta
    err_msg = str(excinfo.value)
    assert missing[0] in err_msg
    assert missing[1] in err_msg
