import subprocess

# Obtener última etiqueta
try:
    last_tag = subprocess.check_output(["git", "describe", "--tags", "--abbrev=0"], text=True).strip()
except subprocess.CalledProcessError:
    last_tag = ""

# Obtener commits desde la última etiqueta
if last_tag:
    commits = subprocess.check_output(["git", "log", f"{last_tag}..HEAD", "--pretty=format:%s"], text=True).splitlines()
else:
    commits = subprocess.check_output(["git", "log", "--pretty=format:%s"], text=True).splitlines()

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

with open("CHANGELOG.md", "w") as f:
    f.write("# Changelog\n\n")
    for section, items in sections.items():
        if items:
            f.write(f"## {section}\n")
            for item in items:
                f.write(f"- {item}\n")
            f.write("\n")

print("Changelog actualizado con secciones")
