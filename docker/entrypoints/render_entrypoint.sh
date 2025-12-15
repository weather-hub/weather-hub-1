#!/bin/bash

# ---------------------------------------------------------------------------
# Script simplificado para Render
# ---------------------------------------------------------------------------

# Detener el script si hay cualquier error
set -e

echo "--> Iniciando proceso de despliegue..."

# 1. Aplicar migraciones SIEMPRE.
# No hace falta comprobar si la DB está vacía. Alembic sabe qué hacer.
# Si ya están las tablas, esto no hará nada (tarda 0.1s).
# Si faltan las tablas, las creará.
echo "--> Ejecutando flask db upgrade..."
flask db upgrade

# 2. Opcional: Seeds
# Si tu comando 'rosemary db:seed' está programado para no duplicar datos
# (ej. comprueba si el usuario existe antes de crearlo), descomenta la siguiente línea:
# echo "--> Ejecutando seeds..."
# rosemary db:seed

# 3. Iniciar la aplicación
echo "--> Iniciando Gunicorn..."
# Usamos exec para que Gunicorn tome el PID 1 (importante para Docker)
exec gunicorn --bind 0.0.0.0:${PORT:-80} app:app --log-level info --timeout 3600