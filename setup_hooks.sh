echo "Instalando hooks de pre-commit..."
pre-commit install
pre-commit install --hook-type commit-msg

# 4. Ejecutar pre-commit en todos los archivos (opcional, recomendado la primera vez)
echo "Ejecutando pre-commit en todos los archivos..."
pre-commit run --all-files

echo "¡Configuración completa! Hooks de pre-commit instalados y activos."