# app/modules/dataset/validators.py
import csv
import os
from typing import List, Tuple

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


def _read_csv_headers_try(path: str, nbytes_sample: int = 8192) -> List[str]:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            sample = fh.read(nbytes_sample)
            fh.seek(0)
            try:
                dialect = csv.Sniffer().sniff(sample)
                delim = dialect.delimiter
            except Exception:
                delim = ","
            reader = csv.reader(fh, delimiter=delim)
            try:
                headers = next(reader)
            except StopIteration:
                headers = []
            headers = [h.strip().lstrip("\ufeff") for h in headers]
            return headers
    except Exception:
        # fallback: try latin1
        with open(path, "r", encoding="latin-1", errors="replace") as fh:
            line = fh.readline()
            headers = [h.strip().lstrip("\ufeff") for h in line.split(",")]
            return headers


def _match_required_in_headers(required: str, headers: List[str]) -> List[str]:
    """
    Return list of headers that match the required token.
    Matching strategy (in order):
      1. exact match
      2. header endswith required (case insensitive)
      3. header contains required as substring (case insensitive)
      4. header contains required without leading underscore
    """
    r = required.lower()
    matches = []
    for h in headers:
        hl = h.lower()
        if hl == r:
            matches.append(h)
            continue
        if hl.endswith(r):
            matches.append(h)
            continue
        if r.strip("_") in hl:
            matches.append(h)
            continue
        # allow station prefix pattern: STATION_token or token_STATION
        if f"_{r.lstrip('_')}" in hl or f"{r.lstrip('_')}" in hl:
            matches.append(h)
    return matches


def validate_dataset_package(
    file_paths: List[str],
    required_columns: List[str] = REQUIRED_COLUMNS,
    max_csv: int = 2,
    require_readme: bool = True,
    exact_match: bool = False,
) -> None:
    """
    Validate a package (list of file paths). Raises ValueError with readable message on failure.
    - Uses pattern-based matching: allowed headers like 'BASEL_temp_mean' satisfy '_temp_mean'
    """
    csv_paths = []
    readme_paths = []
    others = []
    for p in file_paths:
        ext = os.path.splitext(p)[1].lower()
        if ext in (".csv", ".tsv"):
            csv_paths.append(p)
        elif ext in (".md", ".txt"):
            readme_paths.append(p)
        else:
            others.append(p)

    errors = []
    warnings = []

    # cardinality checks
    if len(csv_paths) == 0:
        errors.append("No se subió ningún CSV. Se requiere 1 o 2 CSV.")
    if len(csv_paths) > max_csv:
        errors.append(f"Máximo {max_csv} CSV permitidos; se recibieron {len(csv_paths)}.")
    if require_readme and len(readme_paths) == 0:
        errors.append("Falta README (.md o .txt). Debe incluirse un fichero README.")

    # For each CSV, check headers using pattern matching
    for csvp in csv_paths:
        if not os.path.exists(csvp):
            errors.append(f"CSV no encontrado: {csvp}")
            continue
        headers = _read_csv_headers_try(csvp)
        if not headers:
            errors.append(f"CSV sin cabecera detectada: {os.path.basename(csvp)}")
            continue
        headers_set = {h.strip() for h in headers if h.strip()}

        missing = []
        matched_map = {}  # required -> list of matching headers
        for req in required_columns:
            matches = _match_required_in_headers(req, headers)
            if matches:
                matched_map[req] = matches
            else:
                missing.append(req)

        # extras: headers that do not match any required token
        matched_headers = set(h for v in matched_map.values() for h in v)
        extra_headers = sorted(
            [h for h in headers if h not in matched_headers and h.upper() != "DATE" and h.upper() != "MONTH"]
        )

        if missing:
            errors.append(f"Faltan columnas requeridas en '{os.path.basename(csvp)}': {missing}")

        if extra_headers:
            warnings.append(f"Columnas extra en '{os.path.basename(csvp)}': {extra_headers} (se permiten por patrón)")

    if errors:
        msg_lines = ["Validation failed"]
        for e in errors:
            msg_lines.append(" - " + e)
        if warnings:
            msg_lines.append("Warnings (no bloqueantes):")
            for w in warnings:
                msg_lines.append(" - " + w)
        raise ValueError("\n".join(msg_lines))

    return
