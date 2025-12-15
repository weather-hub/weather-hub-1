#!/bin/bash

# Detener el script si ocurre cualquier error
set -e

echo "--> Iniciando Entrypoint..."

# 1. Aplicar migraciones
# Al estar la base de datos vacía, esto creará todas las tablas.
# En futuros despliegues, solo aplicará cambios nuevos si los hay.
echo "--> Ejecutando migraciones (flask db upgrade)..."
flask db upgrade

# 2. (OPCIONAL) Cargar datos iniciales
# Si necesitas que se cree un usuario admin o datos base, descomenta la siguiente línea.
# SOLO hazlo si tu comando 'db:seed' es inteligente (es decir, que no falla si el usuario ya existe).
rosemary db:seed

# 3. Iniciar el servidor
echo "--> Iniciando Gunicorn..."
exec gunicorn --bind 0.0.0.0:${PORT:-80} app:app --log-level info --timeout 3600