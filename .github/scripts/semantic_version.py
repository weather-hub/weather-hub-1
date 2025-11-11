import subprocess
import semver
import toml

# Cargar pyproject.toml
pyproject_path = "pyproject.toml"
pyproject = toml.load(pyproject_path)

# Leer versión actual desde [project]
version = pyproject["project"]["version"]

# Obtener commits desde la última etiqueta
try:
    last_tag = subprocess.check_output(
        ["git", "describe", "--tags", "--abbrev=0"], text=True
    ).strip()
    commits = subprocess.check_output(
        ["git", "log", f"{last_tag}..HEAD", "--pretty=format:%s"], text=True
    ).splitlines()
except subprocess.CalledProcessError:
    commits = subprocess.check_output(
        ["git", "log", "--pretty=format:%s"], text=True
    ).splitlines()

# Determinar tipo de incremento
bump_type = "patch"
for c in commits:
    if c.startswith("feat"):
        bump_type = "minor"
    elif c.startswith("fix") and bump_type != "minor":
        bump_type = "patch"
    elif c.startswith("BREAKING CHANGE"):
        bump_type = "major"
        break

# Incrementar versión
v = semver.VersionInfo.parse(version)
if bump_type == "major":
    new_version = v.bump_major()
elif bump_type == "minor":
    new_version = v.bump_minor()
else:
    new_version = v.bump_patch()

# Guardar nueva versión de vuelta en pyproject.toml
pyproject["project"]["version"] = str(new_version)
with open(pyproject_path, "w") as f:
    toml.dump(pyproject, f)

print(f"Versión actualizada: {version} -> {new_version}")
