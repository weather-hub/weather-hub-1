import subprocess
import toml
import os
from datetime import datetime

# Cargar pyproject.toml para obtener la versión actual
pyproject_path = "pyproject.toml"
pyproject = toml.load(pyproject_path)
version = pyproject["project"]["version"]

# Obtener última etiqueta (opcional)
try:
    last_tag = subprocess.check_output(
        ["git", "describe", "--tags", "--abbrev=0"], text=True
    ).strip()
except subprocess.CalledProcessError:
    last_tag = ""

# Obtener commits desde la última etiqueta o desde el inicio
if last_tag:
    commits = subprocess.check_output(
        ["git", "log", f"{last_tag}..HEAD", "--pretty=format:%s"], text=True
    ).splitlines()
else:
    commits = subprocess.check_output(
        ["git", "log", "--pretty=format:%s"], text=True
    ).splitlines()

# Clasificar commits por tipo
sections = {
    "Features": [],
    "Fixes": [],
    "Docs": [],
    "Others": []
}

for c in commits:
    if c.startswith("feat"):
        sections["Features"].append(c)
    elif c.startswith("fix"):
        sections["Fixes"].append(c)
    elif c.startswith("docs"):
        sections["Docs"].append(c)
    else:
        sections["Others"].append(c)

# Preparar contenido del changelog
header = f"# Changelog - Version {version} ({datetime.today().strftime('%Y-%m-%d')})\n\n"

changelog_lines = [header]

for section, items in sections.items():
    if items:
        changelog_lines.append(f"## {section}\n")
        for item in items:
            changelog_lines.append(f"- {item}")
        changelog_lines.append("")  # línea en blanco entre secciones

# Guardar en CHANGELOG.md
changelog_path = "CHANGELOG.md"

# Si existe, leerlo y añadir al final para no perder cambios previos
if os.path.exists(changelog_path):
    with open(changelog_path, "r") as f:
        old_content = f.read()
else:
    old_content = ""

# Escribimos la nueva versión al inicio del changelog
with open(changelog_path, "w") as f:
    f.write("\n".join(changelog_lines))
    f.write("\n")
    f.write(old_content)  # conservar el changelog previo

print(f"Changelog actualizado con la versión {version}")
