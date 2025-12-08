import os
import re
import subprocess
import sys
from datetime import datetime

import semver
import tomlkit

# --- CONFIGURACIÓN ---
PYPROJECT_PATH = "pyproject.toml"
CHANGELOG_PATH = "CHANGELOG.md"


def get_git_history():
    """Devuelve (ultimo_tag, lista_commits)."""
    try:
        last_tag = subprocess.check_output(["git", "describe", "--tags", "--abbrev=0"], text=True).strip()
    except subprocess.CalledProcessError:
        last_tag = None

    cmd = ["git", "log", "--pretty=format:%s"]
    if last_tag:
        cmd.insert(2, f"{last_tag}..HEAD")

    try:
        commits = subprocess.check_output(cmd, text=True).strip().splitlines()
    except subprocess.CalledProcessError:
        commits = []

    return last_tag, [c for c in commits if c]  # Filtrar líneas vacías


def analyze_commits(commits):
    """Clasifica commits y decide el tipo de incremento."""
    sections = {"Features": [], "Fixes": [], "Breaking Changes": [], "Others": []}
    bump_type = None

    for c in commits:
        # Clasificación para Changelog
        if "BREAKING CHANGE" in c:
            sections["Breaking Changes"].append(c)
        elif c.startswith("feat"):
            sections["Features"].append(c)
        elif c.startswith("fix"):
            sections["Fixes"].append(c)
        else:
            # Ignoramos commits de coreografía o del propio bot
            if not c.startswith("chore(release)"):
                sections["Others"].append(c)

        # Decisión de Versionado
        if "BREAKING CHANGE" in c:
            bump_type = "major"
        elif c.startswith("feat") and bump_type != "major":
            bump_type = "minor"
        elif c.startswith("fix") and bump_type not in ["major", "minor"]:
            bump_type = "patch"

    return bump_type, sections


def update_pyproject(new_version):
    """Actualiza pyproject.toml preservando formato."""
    with open(PYPROJECT_PATH, "r", encoding="utf-8") as f:
        data = tomlkit.load(f)

    # Soporte dual: [project] o [tool.poetry]
    if "project" in data and "version" in data["project"]:
        data["project"]["version"] = str(new_version)
    elif "tool" in data and "poetry" in data["tool"]:
        data["tool"]["poetry"]["version"] = str(new_version)
    else:
        raise KeyError("No se encontró la clave de versión en pyproject.toml")

    with open(PYPROJECT_PATH, "w", encoding="utf-8") as f:
        tomlkit.dump(data, f)


def update_changelog(new_version, sections):
    """Genera y escribe el changelog."""
    date_str = datetime.today().strftime("%Y-%m-%d")
    header = f"# Version {new_version} ({date_str})"

    # Construir cuerpo del mensaje
    lines = [header, ""]
    # Prioridad de orden en el changelog
    order = ["Breaking Changes", "Features", "Fixes", "Others"]

    has_content = False
    for sec in order:
        items = sections.get(sec, [])
        if items:
            has_content = True
            lines.append(f"## {sec}")
            for item in items:
                lines.append(f"- {item}")
            lines.append("")

    if not has_content:
        return False

    new_block = "\n".join(lines)

    # Leer archivo existente
    old_content = ""
    if os.path.exists(CHANGELOG_PATH):
        with open(CHANGELOG_PATH, "r", encoding="utf-8") as f:
            old_content = f.read()

    # Reemplazar si ya existe la cabecera (re-run) o insertar nuevo
    if old_content.strip().startswith(f"# Version {new_version}"):
        # Buscamos el siguiente header para cortar
        match = re.search(r"\n# Version ", old_content[1:])
        if match:
            rest = old_content[match.start() + 1 :]
            final_content = new_block + "\n" + rest
        else:
            final_content = new_block + "\n"
    else:
        final_content = new_block + "\n\n" + old_content

    with open(CHANGELOG_PATH, "w", encoding="utf-8") as f:
        f.write(final_content)

    return True


def main():
    print("--- Iniciando Gestor de Releases ---")

    # 1. Leer versión actual
    with open(PYPROJECT_PATH, "r", encoding="utf-8") as f:
        data = tomlkit.load(f)
        # Intenta obtener version de project o poetry
        try:
            current_version = data["project"]["version"]
        except KeyError:
            current_version = data["tool"]["poetry"]["version"]

    print(f"Versión actual: {current_version}")

    # 2. Analizar Git
    last_tag, commits = get_git_history()
    bump_type, sections = analyze_commits(commits)

    if not bump_type:
        print(">> No hay cambios relevantes. Terminando.")
        if "GITHUB_OUTPUT" in os.environ:
            with open(os.environ["GITHUB_OUTPUT"], "a") as gh:
                gh.write("released=false\n")
        sys.exit(0)

    # 3. Calcular nueva versión
    v = semver.VersionInfo.parse(current_version)
    if bump_type == "major":
        new_v = v.bump_major()
    elif bump_type == "minor":
        new_v = v.bump_minor()
    else:
        new_v = v.bump_patch()

    print(f">> Incremento: {bump_type}. Nueva versión: {new_v}")

    # 4. Modificar Archivos
    update_pyproject(new_v)
    update_changelog(new_v, sections)

    # 5. Output para GitHub Actions
    if "GITHUB_OUTPUT" in os.environ:
        with open(os.environ["GITHUB_OUTPUT"], "a") as gh:
            gh.write("released=true\n")
            gh.write(f"version={new_v}\n")


if __name__ == "__main__":
    main()
