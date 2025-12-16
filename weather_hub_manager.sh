#!/bin/bash

# ==========================================
# 0. AUTO-ELEVACIÓN Y DETECCIÓN DE USUARIO
# ==========================================
# Si no soy root, me reinicio con sudo automáticamente
if [[ $EUID -ne 0 ]]; then
   echo "Necesito permisos de administrador para gestionar puertos y servicios."
   echo "Elevando privilegios..."
   exec sudo /bin/bash "$0" "$@"
fi

# Detectamos quién es el usuario real (el humano que está tecleando)
REAL_USER=${SUDO_USER:-$USER}
USER_GROUP=$(id -gn $REAL_USER)

# ==========================================
# 1. TRAMPA DE SEGURIDAD (ANTI-BLOQUEOS)
# ==========================================
# Esta función se ejecuta SIEMPRE al final, pase lo que pase.
cleanup_and_exit() {
    echo ""
    echo -e "\033[0;34m[Script] Finalizando... Devolviendo permisos de archivos a $REAL_USER...\033[0m"

    # 1. Devolvemos la propiedad de TODO el directorio al usuario real
    # Esto evita que aparezcan candados en tus archivos.
    chown -R $REAL_USER:$USER_GROUP .

    # 2. Borramos basura compilada por root (opcional, buena práctica)
    find . -name "__pycache__" -exec rm -rf {} + > /dev/null 2>&1

    echo -e "\033[0;32m✔ Listo. Todos los archivos son tuyos de nuevo.\033[0m"
}

# Activamos la trampa para: Salida Normal, CTRL+C (SIGINT), Kill (SIGTERM)
trap cleanup_and_exit EXIT SIGINT SIGTERM

# ==========================================
# COLORES Y ESTILOS
# ==========================================
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m' # No Color

# ==========================================
# FUNCIONES DE ESTADO Y UTILIDAD
# ==========================================

# Comprueba si un puerto está en uso
check_port() {
    (echo >/dev/tcp/localhost/$1) &>/dev/null && echo "UP" || echo "DOWN"
}

get_service_status() {
    # Estado Docker
    if docker compose -f docker/docker-compose.dev.yml ps | grep "Up" > /dev/null 2>&1; then
        DOCKER_STATUS="${GREEN}● ACTIVO${NC}"
        DOCKER_RUNNING=true
    else
        DOCKER_STATUS="${RED}○ INACTIVO${NC}"
        DOCKER_RUNNING=false
    fi

    # Estado Puerto 5000 (Flask/Native/Vagrant)
    if [[ $(check_port 5000) == "UP" ]]; then
        PORT5000_STATUS="${GREEN}● OCUPADO${NC}"
        PORT5000_RUNNING=true
    else
        PORT5000_STATUS="${RED}○ LIBRE${NC}"
        PORT5000_RUNNING=false
    fi
}

print_header() {
    get_service_status
    clear
    echo -e "${BLUE}================================================================${NC}"
    echo -e "${CYAN}             WEATHER HUB - GESTOR (MODO ROOT)            ${NC}"
    echo -e "${BLUE}================================================================${NC}"
    echo -e "   Usuario Real:  ${YELLOW}$REAL_USER${NC}"
    echo -e "   ${MAGENTA}ESTADO ACTUAL DEL SISTEMA:${NC}"
    echo -e "   [Docker]:      $DOCKER_STATUS"
    echo -e "   [Puerto 5000]: $PORT5000_STATUS"
    echo -e "${BLUE}================================================================${NC}"
    echo ""
}

pause() {
    echo ""
    read -p "Presiona [Enter] para continuar..."
}

check_root_dir() {
    if [[ ! -f "requirements.txt" ]]; then
        echo -e "${RED}[ERROR] No parece que estés en la raíz del proyecto Weather Hub.${NC}"
        # Forzamos exit para que salte el trap y arregle permisos por si acaso
        exit 1
    fi
}

switch_env() {
    local source_file=$1
    echo -e "${BLUE}ℹ Configurando variables de entorno...${NC}"
    cp "$source_file" .env
    # Permiso inmediato para lectura
    chown $REAL_USER:$USER_GROUP .env
    echo -e "${GREEN}✔ Archivo .env actualizado desde $source_file${NC}"
}

ensure_clean_slate() {
    local target_method=$1

    echo -e "${YELLOW}>>> Verificando conflictos para iniciar modo $target_method...${NC}"

    # Caso 1: Docker bloqueando
    if [[ "$target_method" != "docker" ]] && [[ "$DOCKER_RUNNING" == true ]]; then
        echo -e "${RED}[!] CONFLICTO DETECTADO:${NC} Docker está corriendo."
        read -p "¿Detener Docker? (s/n): " stop_d
        if [[ "$stop_d" == "s" ]]; then
            docker compose -f docker/docker-compose.dev.yml down
            DOCKER_RUNNING=false
        else
            return 1
        fi
    fi

    # Caso 2: Puerto 5000 ocupado
    if [[ "$target_method" == "docker" ]] && [[ "$PORT5000_RUNNING" == true ]]; then
        echo -e "${RED}[!] CONFLICTO DETECTADO:${NC} Puerto 5000 ocupado."
        read -p "¿Forzar detención del proceso en puerto 5000? (s/n): " kill_p
        if [[ "$kill_p" == "s" ]]; then
            fuser -k 5000/tcp > /dev/null 2>&1
            echo -e "${GREEN}Proceso detenido.${NC}"
        else
            return 1
        fi
    fi
    return 0
}

# ==========================================
# MÉTODOS: NATIVO (MANUAL)
# ==========================================
setup_native() {
    echo -e "${YELLOW}>>> Instalando dependencias Nativas (Como Root)...${NC}"

    if ! command -v python3.12 &> /dev/null; then
        echo -e "${RED}[Error] Python 3.12 no detectado.${NC}"
        pause; return
    fi

    echo "webhook" > .moduleignore

    # Crear entorno virtual
    python3.12 -m venv venv
    source venv/bin/activate
    pip install --upgrade pip

    echo "Instalando dependencias..."
    pip install -r requirements.txt
    pip install -e ./

    echo -e "${GREEN}>>> Setup Nativo listo.${NC}"

    systemctl start mariadb
    echo -e "${BLUE}Nota: MariaDB iniciada.${NC}"

    read -p "¿Quieres poblar la base de datos ahora (db:seed)? (s/n): " confirm
    if [[ "$confirm" == "s" ]]; then
        switch_env ".env.local.example"

        echo -e "${YELLOW}>>> Reseteando DB...${NC}"
        # Como somos root, rosemary no tendrá problemas de permisos de escritura
        rosemary db:reset -y
        rosemary db:seed
    fi
    pause
}

run_native() {
    ensure_clean_slate "native" || return
    systemctl start mariadb
    switch_env ".env.local.example"

    echo -e "${YELLOW}>>> Ejecutando entorno Nativo (Flask)...${NC}"
    if [[ ! -d "venv" ]]; then
        echo -e "${RED}[Error] Entorno virtual no encontrado.${NC}"; pause; return
    fi

    source venv/bin/activate
    echo -e "${GREEN}Servidor iniciándose en http://localhost:5000${NC}"
    echo "Presiona CTRL+C para detener."

    # Ejecutamos Flask. Al cerrar con CTRL+C, saltará el TRAP y arreglará permisos.
    flask run --host=0.0.0.0 --reload --debug
    pause
}

# ==========================================
# MÉTODOS: DOCKER
# ==========================================
# Docker funciona mejor como root/sudo, así que esto es ideal.

setup_docker() {
    echo -e "${YELLOW}>>> Preparando imágenes Docker...${NC}"
    systemctl stop mariadb
    docker compose -f docker/docker-compose.dev.yml up -d --build
    echo -e "${GREEN}>>> Imágenes construidas.${NC}"
    pause
}

run_docker() {
    ensure_clean_slate "docker" || return
    systemctl stop mariadb
    switch_env ".env.docker.example"

    echo -e "${YELLOW}>>> Levantando contenedores...${NC}"
    docker compose -f docker/docker-compose.dev.yml up -d
    echo -e "${GREEN}>>> Contenedores activos.${NC}"
    pause
}

stop_docker() {
    echo -e "${YELLOW}>>> Deteniendo entorno Docker...${NC}"
    docker compose -f docker/docker-compose.dev.yml down
    pause
}

reset_docker() {
    echo -e "${RED}>>> ¡ATENCIÓN! RESET TOTAL DE DOCKER <<<${NC}"
    echo "Se eliminarán contenedores y VOLÚMENES (Datos)."
    read -p "¿Estás seguro? (escribe 'si'): " confirm
    if [[ "$confirm" == "si" ]]; then
        docker compose -f docker/docker-compose.dev.yml down -v
        echo -e "${GREEN}>>> Sistema limpio.${NC}"
    fi
    pause
}

# ==========================================
# MÉTODOS: VAGRANT
# ==========================================
# Vagrant NO debe correr como root directo.
# Usamos 'sudo -u $REAL_USER' para invocar los comandos de vagrant.

setup_vagrant() {
    echo -e "${YELLOW}>>> Limpiando para Vagrant...${NC}"
    # Como somos root, el rm nunca falla
    rm -rf uploads rosemary.egg-info app.log*
    echo -e "${GREEN}>>> Archivos preparados.${NC}"
    pause
}

run_vagrant() {
    ensure_clean_slate "vagrant" || return

    # Copiamos env, pero aseguramos permisos al momento para que Vagrant lo lea
    cp .env.vagrant.example .env
    chown $REAL_USER:$USER_GROUP .env

    cd vagrant || return
    echo -e "${YELLOW}>>> Iniciando VM (Como usuario $REAL_USER)...${NC}"

    # COMANDO CRÍTICO: Ejecutar como usuario normal
    sudo -u $REAL_USER vagrant up

    echo -e "${GREEN}>>> VM Iniciada. Conectando SSH...${NC}"
    sudo -u $REAL_USER vagrant ssh
    cd ..
}

destroy_vagrant() {
    echo -e "${YELLOW}>>> Destruyendo VM...${NC}"
    cd vagrant || return
    sudo -u $REAL_USER vagrant destroy -f

    # Limpieza profunda de carpeta .vagrant
    rm -rf .vagrant

    cd ..
    echo -e "${GREEN}>>> VM Eliminada.${NC}"
    pause
}

# ==========================================
# MENÚ PRINCIPAL
# ==========================================

check_root_dir

while true; do
    print_header
    echo -e "${CYAN}--- NATIVO (Local) ---${NC}"
    echo " 1. Setup (Instalar dependencias + Seed BD)"
    echo " 2. Run (Flask Server)"
    echo ""
    echo -e "${CYAN}--- DOCKER (Contenedores) ---${NC}"
    echo " 3. Setup (Build Images)"
    echo " 4. Run (Up)"
    echo " 5. Stop"
    echo -e "${RED} 6. RESET (Borrar Datos Docker)${NC}"
    echo ""
    echo -e "${CYAN}--- VAGRANT (Máquina Virtual) ---${NC}"
    echo " 7. Limpiar conflictos"
    echo " 8. Run (Up + SSH) [Modo Usuario Seguro]"
    echo " 9. Destruir VM"
    echo ""
    echo " 10. Salir (Arregla permisos al salir)"
    echo ""
    read -p "Selecciona: " opcion

    case $opcion in
        1) setup_native ;;
        2) run_native ;;
        3) setup_docker ;;
        4) run_docker ;;
        5) stop_docker ;;
        6) reset_docker ;;
        7) setup_vagrant ;;
        8) run_vagrant ;;
        9) destroy_vagrant ;;
        10) exit 0 ;; # Al salir, salta el 'trap' y arregla permisos
        *) echo -e "${RED}Opción no válida.${NC}"; pause ;;
    esac
done
