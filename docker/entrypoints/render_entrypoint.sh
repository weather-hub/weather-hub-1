#!/bin/bash
set -e

echo "================================================="
echo "   REPARACIÓN DE BASE DE DATOS (ZOMBIE FIX)    "
echo "================================================="

# 1. EL TRUCO: Borrar la tabla de versiones manualmente.
# Esto obliga a Alembic a creer que es una instalación nueva.
echo "--> [1/3] Eliminando rastro corrupto de 'alembic_version'..."
mariadb -u $MARIADB_USER -p$MARIADB_PASSWORD -h $MARIADB_HOSTNAME -P $MARIADB_PORT -D $MARIADB_DATABASE -e "DROP TABLE IF EXISTS alembic_version;"

# 2. Ahora sí, ejecutamos la migración.
# Como borramos la versión, Alembic intentará crear todas las tablas.
echo "--> [2/3] Ejecutando: flask db upgrade"
flask db upgrade

# 3. Iniciar la aplicación
echo "--> [3/3] Iniciando Gunicorn..."
exec gunicorn --bind 0.0.0.0:${PORT:-80} app:app --log-level info --timeout 3600