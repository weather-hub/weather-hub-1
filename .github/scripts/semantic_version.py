import subprocess

import semver
import toml

# Cargar versión actual
pyproject = toml.load("pyproject.toml")
version = semver.VersionInfo.parse(pyproject["project"]["version"])

# Obtener commits desde última tag
try:
    last_tag = subprocess.run(
        ["git", "describe", "--tags", "--abbrev=0"], capture_output=True, text=True, check=True
    ).stdout.strip()
    range_commits = f"{last_tag}..HEAD"
except subprocess.CalledProcessError:
    range_commits = "HEAD"

commits = subprocess.run(["git", "log", range_commits, "--pretty=format:%s"], capture_output=True, text=True).stdout

# Determinar incremento (prioridad: major > minor > patch)
if "BREAKING CHANGE" in commits:
    new_version = version.bump_major()
elif commits.startswith("feat") or "\nfeat" in commits:
    new_version = version.bump_minor()
else:
    new_version = version.bump_patch()

# Guardar
pyproject["project"]["version"] = str(new_version)
with open("pyproject.toml", "w") as f:
    toml.dump(pyproject, f)

print(f"{version} -> {new_version}")
