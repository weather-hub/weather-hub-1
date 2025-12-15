#!/bin/bash

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
    echo -e "${CYAN}             WEATHER HUB - GESTOR DE ENTORNO             ${NC}"
    echo -e "${BLUE}================================================================${NC}"
    echo -e "   ${MAGENTA}ESTADO ACTUAL DEL SISTEMA:${NC}"
    echo -e "   [Docker]:      $DOCKER_STATUS"
    echo -e "   [Puerto 5000]: $PORT5000_STATUS (Usado por Native o Vagrant)"
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
        exit 1
    fi
}

# Cambia el archivo .env según el modo elegido
switch_env() {
    local source_file=$1
    echo -e "${BLUE}ℹ Configurando variables de entorno para este modo...${NC}"
    cp "$source_file" .env
    echo -e "${GREEN}✔ Archivo .env actualizado desde $source_file${NC}"
}

# Función inteligente para evitar conflictos
ensure_clean_slate() {
    local target_method=$1 # "native", "docker", "vagrant"

    echo -e "${YELLOW}>>> Verificando conflictos para iniciar modo $target_method...${NC}"

    # Caso 1: Quiero iniciar NATIVE/VAGRANT pero Docker está corriendo
    if [[ "$target_method" != "docker" ]] && [[ "$DOCKER_RUNNING" == true ]]; then
        echo -e "${RED}[!] CONFLICTO DETECTADO:${NC} Docker está corriendo y bloqueará los puertos."
        read -p "¿Quieres detener Docker automáticamente antes de seguir? (s/n): " stop_d
        if [[ "$stop_d" == "s" ]]; then
            echo "Deteniendo Docker..."
            docker compose -f docker/docker-compose.dev.yml down
            DOCKER_RUNNING=false
        else
            echo -e "${RED}Cancelando operación para evitar errores.${NC}"
            pause
            return 1
        fi
    fi

    # Caso 2: Quiero iniciar DOCKER pero el puerto 5000 está ocupado (Native/Vagrant)
    if [[ "$target_method" == "docker" ]] && [[ "$PORT5000_RUNNING" == true ]]; then
        echo -e "${RED}[!] CONFLICTO DETECTADO:${NC} Algo está usando el puerto 5000 (posiblemente Native o Vagrant)."
        echo "Docker fallará si no liberas el puerto."
        read -p "¿Quieres intentar matar el proceso en el puerto 5000? (s/n): " kill_p
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
    echo -e "${YELLOW}>>> Instalando dependencias Nativas...${NC}"

    if ! command -v python3.12 &> /dev/null; then
        echo -e "${RED}[Error] Python 3.12 no detectado.${NC}"
        pause; return
    fi

    echo "webhook" > .moduleignore

    python3.12 -m venv venv
    source venv/bin/activate
    pip install --upgrade pip
    echo "Instalando dependencias (esto puede tardar)..."
    pip install -r requirements.txt
    pip install -e ./
    echo -e "${GREEN}>>> Setup Nativo listo.${NC}"

    # Asegúrate de que MariaDB esté corriendo
    sudo systemctl start mariadb

    echo -e "${BLUE}Nota: Asegúrate de tener MariaDB corriendo.${NC}"
    read -p "¿Quieres poblar la base de datos ahora (db:seed)? (s/n): " confirm
    if [[ "$confirm" == "s" ]]; then
        # Aseguramos el env correcto temporalmente
        switch_env ".env.local.example"

        # --- FIX: Arreglamos permisos antes de borrar ---
        echo -e "${YELLOW}>>> Ajustando permisos de archivos antes del reset...${NC}"
        sudo chown -R $USER:$USER .

        # Ahora sí, ejecutamos sin miedo
        rosemary db:reset -y
        rosemary db:seed

    fi
    pause
}

run_native() {
    # 1. Verificar limpieza
    ensure_clean_slate "native" || return
    sudo systemctl start mariadb
    # 2. Configurar ENV
    switch_env ".env.local.example"

    # 3. Ejecutar
    echo -e "${YELLOW}>>> Ejecutando entorno Nativo...${NC}"
    if [[ ! -d "venv" ]]; then
        echo -e "${RED}[Error] Entorno virtual no encontrado. Ejecuta Setup primero.${NC}"; pause; return
    fi

    source venv/bin/activate
    echo -e "${GREEN}Servidor iniciándose en http://localhost:5000${NC}"
    echo "Presiona CTRL+C para detener."
    flask run --host=0.0.0.0 --reload --debug
    pause
}

# ==========================================
# MÉTODOS: DOCKER
# ==========================================

setup_docker() {
    echo -e "${YELLOW}>>> Preparando imágenes Docker...${NC}"
    if ! command -v docker &> /dev/null; then echo -e "${RED}[Error] Docker no instalado.${NC}"; return; fi
    sudo systemctl stop mariadb
    docker compose -f docker/docker-compose.dev.yml up -d --build
    echo -e "${GREEN}>>> Imágenes construidas.${NC}"
    pause
}

run_docker() {
    # 1. Verificar limpieza
    ensure_clean_slate "docker" || return
    sudo systemctl stop mariadb
    # 2. Configurar ENV
    switch_env ".env.docker.example"

    # 3. Ejecutar
    echo -e "${YELLOW}>>> Levantando contenedores...${NC}"
    docker compose -f docker/docker-compose.dev.yml up -d

    echo -e "${GREEN}>>> Contenedores activos.${NC}"
    echo "App disponible en http://localhost"
    pause
}

stop_docker() {
    echo -e "${YELLOW}>>> Deteniendo entorno Docker...${NC}"
    docker compose -f docker/docker-compose.dev.yml down
    echo -e "${GREEN}>>> Contenedores detenidos.${NC}"
    pause
}

reset_docker() {
    echo -e "${RED}>>> ¡ATENCIÓN! ESTA ACCIÓN ES DESTRUCTIVA <<<${NC}"
    echo "Se detendrán los contenedores y SE BORRARÁ LA BASE DE DATOS (Volúmenes)."
    echo "Perderás todos los datos guardados en Docker."

    read -p "¿Estás seguro? (escribe 'si' para confirmar): " confirm
    if [[ "$confirm" == "si" ]]; then
        echo -e "${YELLOW}>>> Reiniciando entorno Docker de fábrica...${NC}"
        docker compose -f docker/docker-compose.dev.yml down -v
        echo -e "${GREEN}>>> Sistema limpio. Ejecuta 'Run Docker' para regenerar la BBDD.${NC}"
    else
        echo "Operación cancelada."
    fi
    pause
}

# ==========================================
# MÉTODOS: VAGRANT
# ==========================================

setup_vagrant() {
    echo -e "${YELLOW}>>> Preparando Vagrant...${NC}"
    echo "Limpiando archivos conflictivos..."
    rm -r uploads
    rm -r -f rosemary.egg-info
    rm  app.log*
    echo -e "${GREEN}>>> Archivos preparados.${NC}"
    pause
}

run_vagrant() {
    # 1. Verificar limpieza
    ensure_clean_slate "vagrant" || return

    # 2. Configurar ENV (Vagrant lo hace dentro, pero copiamos el base por si acaso)
    if [[ ! -f ".env" ]]; then cp .env.vagrant.example .env; fi

    cd vagrant || return

    echo -e "${YELLOW}>>> Iniciando Máquina Virtual...${NC}"
    vagrant up
    echo -e "${GREEN}>>> VM Iniciada. Conectando SSH...${NC}"
    vagrant ssh
    cd ..
}

rerun_vagrant() {
    # 1. Verificar limpieza
    ensure_clean_slate "vagrant" || return

    # 2. Configurar ENV (Vagrant lo hace dentro, pero copiamos el base por si acaso)
    if [[ ! -f ".env" ]]; then cp .env.vagrant.example .env; fi

    cd vagrant || return

    echo -e "${YELLOW}>>> Iniciando Máquina Virtual...${NC}"
    vagrant up --provision
    echo -e "${GREEN}>>> VM Iniciada. Conectando SSH...${NC}"
    vagrant ssh
    cd ..
}

reload_vagrant() {
    # 1. Verificar limpieza
    ensure_clean_slate "vagrant" || return

    # 2. Configurar ENV (Vagrant lo hace dentro, pero copiamos el base por si acaso)
    if [[ ! -f ".env" ]]; then cp .env.vagrant.example .env; fi

    cd vagrant || return

    echo -e "${YELLOW}>>> Iniciando Máquina Virtual...${NC}"
    vagrant reload --provision
    echo -e "${GREEN}>>> VM recargada. Conectando SSH...${NC}"
    vagrant ssh
    cd ..
}

stop_vagrant() {
    echo -e "${YELLOW}>>> Deteniendo Vagrant...${NC}"
    cd vagrant || return
    vagrant halt
    cd ..
    echo -e "${GREEN}>>> VM Detenida.${NC}"
    pause
}

destroy_vagrant() {
    echo -e "${YELLOW}>>> Destruyendo maquina virtual...${NC}"
    cd vagrant || return
    vagrant destroy
    rm -r .vagrant
    cd ..
    echo -e "${GREEN}>>> VM Detenida.${NC}"
    pause
}

# ==========================================
# MENÚ PRINCIPAL
# ==========================================

check_root_dir

while true; do
    print_header
    echo -e "${CYAN}--- MÉTODO A: NATIVO (LINUX) ---${NC}"
    echo " 1. Setup y repopular base de datos (Instala dependencias pero hace falta tener la BD instalada, no cambia migraciones)"
    echo " 2. Run (Ejecutar Servidor - Puerto 5000)"
    echo ""
    echo -e "${CYAN}--- MÉTODO B: DOCKER ---${NC}"
    echo " 3. Setup (Construir imágenes)"
    echo " 4. Run (Levantar Contenedores - Puerto 80)"
    echo " 5. Stop (Detener - Mantiene datos)"
    echo -e "${RED} 6. RESET (Detener - BORRA DATOS)${NC}"
    echo ""
    echo -e "${CYAN}--- MÉTODO C: VAGRANT ---${NC}"
    echo " 7. Limpiar conflictos (Preparar archivos)"
    echo " 8. Run (Iniciar y SSH)"
    echo " 9. Apagar (Eliminar VM)"
    echo ""
    echo -e "${CYAN}--- OTROS ---${NC}"
    echo " 10. Salir"
    echo ""
    read -p "Selecciona una opción [1-10]: " opcion

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
        10) echo "Saliendo..."; exit 0 ;;
        *) echo -e "${RED}Opción no válida.${NC}"; pause ;;
    esac
done
