import os
import subprocess
from datetime import datetime

import toml

# Cargar versión actual
pyproject = toml.load("pyproject.toml")
version = pyproject["project"]["version"]

# Obtener commits desde última tag
try:
    last_tag = subprocess.run(
        ["git", "describe", "--tags", "--abbrev=0"], capture_output=True, text=True, check=True
    ).stdout.strip()
    range_commits = f"{last_tag}..HEAD"
except subprocess.CalledProcessError:
    range_commits = "HEAD"

commits = subprocess.run(
    ["git", "log", range_commits, "--pretty=format:%s"], capture_output=True, text=True
).stdout.splitlines()

# Clasificar commits por tipo
sections = {"Features": [], "Fixes": [], "Docs": [], "Others": []}

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
