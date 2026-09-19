#!/usr/bin/env bash
#
# Prepara o ambiente para ESTA máquina:
#   1. gera o .env com UID/GID do usuário e os GIDs de video e render
#   2. garante que o arquivo de autoridade do X exista
#   3. clona o limo_ros2 e aplica as correções de patches/
#   4. clona o livox_ros_driver2 (mensagem CustomMsg do FAST_LIO)
#   5. clona o ros2_livox_simulation (sensor Mid-360 no Gazebo)
#   6. clona o mrs_gazebo_common_resources (grass_plane do mundo floresta)
#
# Idempotente: rodar de novo não estraga nada.

set -euo pipefail
cd "$(dirname "$0")"

REPO_URL="https://github.com/agilexrobotics/limo_ros2.git"
REPO_BRANCH="humble"
UPSTREAM_COMMIT="dcc5a86"
PATCH="patches/limo_ros2-fixes.patch"
SRC_DIR="ws/src/limo_ros2"

say() { printf '\n\033[1m==> %s\033[0m\n' "$1"; }
warn() { printf '    AVISO: %s\n' "$1"; }

# ---------------------------------------------------------------- 1. .env
say "Detectando IDs desta máquina"

USER_UID="$(id -u)"
USER_GID="$(id -g)"

VIDEO_GID="$(getent group video | cut -d: -f3 || true)"
RENDER_GID="$(getent group render | cut -d: -f3 || true)"

if [ -z "${VIDEO_GID}" ]; then
    warn "grupo 'video' não existe; usando 44 como palpite"
    VIDEO_GID=44
fi
if [ -z "${RENDER_GID}" ]; then
    warn "grupo 'render' não existe; repetindo o GID de video"
    RENDER_GID="${VIDEO_GID}"
fi

# Em GNOME/Wayland o Xwayland usa .mutter-Xwaylandauth em /run, não
# ~/.Xauthority. XAUTHORITY, quando definido, aponta para o arquivo certo.
XAUTH_FILE="${XAUTHORITY:-${HOME}/.Xauthority}"

cat > .env <<EOF
# Gerado por setup.sh em $(date -Iseconds). Não versionado: é desta máquina.
USER_UID=${USER_UID}
USER_GID=${USER_GID}
VIDEO_GID=${VIDEO_GID}
RENDER_GID=${RENDER_GID}
XAUTH_FILE=${XAUTH_FILE}

# Mude se 42 colidir com outro container ROS nesta máquina
ROS_DOMAIN_ID=42
EOF

echo "    USER_UID=${USER_UID}  USER_GID=${USER_GID}"
echo "    VIDEO_GID=${VIDEO_GID}  RENDER_GID=${RENDER_GID}"
echo "    XAUTH_FILE=${XAUTH_FILE}"

# ------------------------------------------------------------ 2. X11
say "Verificando o acesso gráfico"

if [ -z "${DISPLAY:-}" ]; then
    warn "DISPLAY está vazio. Rode o setup a partir de um terminal da sessão"
    warn "gráfica, senão o Gazebo e o RViz não terão onde desenhar."
else
    echo "    DISPLAY=${DISPLAY}"
fi

if [ ! -e "${XAUTH_FILE}" ]; then
    touch "${XAUTH_FILE}"
    echo "    criado ${XAUTH_FILE} (vazio)"
else
    echo "    ${XAUTH_FILE} já existe"
fi

if [ ! -d /dev/dri ]; then
    warn "/dev/dri não existe nesta máquina (VM, WSL ou servidor headless?)."
    warn "O 'docker compose up' vai falhar. Remova a seção 'devices:' do"
    warn "docker-compose.yml para rodar sem aceleração gráfica."
fi

# ------------------------------------------------- 3. limo_ros2 + patch
say "Preparando o limo_ros2"

mkdir -p ws/src

if [ -d "${SRC_DIR}/.git" ]; then
    echo "    ${SRC_DIR} já existe, nada a fazer"
    echo "    (para refazer do zero: rm -rf ${SRC_DIR} && ./setup.sh)"
else
    git clone -q -b "${REPO_BRANCH}" "${REPO_URL}" "${SRC_DIR}"
    echo "    clonado em ${SRC_DIR}"

    if git -C "${SRC_DIR}" am < "${PATCH}" 2>/dev/null; then
        echo "    correções aplicadas"
    else
        git -C "${SRC_DIR}" am --abort 2>/dev/null || true
        warn "git am falhou (o upstream provavelmente mudou). Tentando 3-way..."
        if git -C "${SRC_DIR}" am --3way < "${PATCH}"; then
            echo "    correções aplicadas com merge de 3 vias"
        else
            git -C "${SRC_DIR}" am --abort 2>/dev/null || true
            warn "não foi possível aplicar ${PATCH} automaticamente."
            warn "Veja a seção de versionamento do README.md."
            exit 1
        fi
    fi
fi

# --------------------------------------------- 4. livox_ros_driver2
say "Preparando o livox_ros_driver2"

LIVOX_DRIVER_DIR="ws/src/livox_ros_driver2"

if [ -d "${LIVOX_DRIVER_DIR}/.git" ]; then
    echo "    ${LIVOX_DRIVER_DIR} já existe, nada a fazer"
else
    # O upstream não tem branch separada para Humble: o CMakeLists se adapta
    # pelo argumento DISTRO_ROS=humble, fixado nos defaults do colcon (Dockerfile).
    git clone -q --depth 1 \
        https://github.com/Livox-SDK/livox_ros_driver2.git "${LIVOX_DRIVER_DIR}"
    echo "    clonado em ${LIVOX_DRIVER_DIR}"
fi

# O repositório guarda package.xml e launch/ do ROS 2 com sufixo _ROS2; o
# colcon só enxerga o pacote depois de copiá-los para os nomes canônicos.
cp -f "${LIVOX_DRIVER_DIR}/package_ROS2.xml" "${LIVOX_DRIVER_DIR}/package.xml"
rm -rf "${LIVOX_DRIVER_DIR}/launch"
cp -r "${LIVOX_DRIVER_DIR}/launch_ROS2" "${LIVOX_DRIVER_DIR}/launch"
echo "    package.xml e launch/ do ROS 2 preparados"

# ------------------------------------------ 5. ros2_livox_simulation
say "Preparando o ros2_livox_simulation (sensor Livox Mid-360 no Gazebo)"

LIVOX_SIM_DIR="ws/src/ros2_livox_simulation"

if [ -d "${LIVOX_SIM_DIR}/.git" ]; then
    echo "    ${LIVOX_SIM_DIR} já existe, nada a fazer"
else
    git clone -q --depth 1 \
        https://github.com/stm32f303ret6/livox_laser_simulation_RO2.git \
        "${LIVOX_SIM_DIR}"
    echo "    clonado em ${LIVOX_SIM_DIR}"
fi

# --------------------------------- 6. mrs_gazebo_common_resources
say "Preparando o mrs_gazebo_common_resources (grass_plane do mundo floresta)"

MRS_DIR="ws/src/mrs_gazebo_common_resources"

if [ -d "${MRS_DIR}/.git" ]; then
    echo "    ${MRS_DIR} já existe, nada a fazer"
else
    git clone -q --depth 1 --branch master \
        https://github.com/ctu-mrs/mrs_gazebo_common_resources.git "${MRS_DIR}"
    echo "    clonado em ${MRS_DIR}"
fi

# É um pacote ROS 1 (catkin) e só os modelos interessam aqui. O COLCON_IGNORE
# evita que o colcon tente compilá-lo e derrube o build do workspace.
touch "${MRS_DIR}/COLCON_IGNORE"
echo "    COLCON_IGNORE criado (o colcon não compila este pacote)"

say "Pronto"
cat <<'EOF'
    Próximos passos:

      docker compose build
      docker compose up -d
      docker compose exec limo bash

    E, dentro do container:

      cd ~/ws
      sudo apt-get update
      rosdep install --from-paths src --ignore-src -r -y
      colcon build --symlink-install
      source install/setup.bash

    O FAST_LIO não é clonado por este script. Quando o pacote do colega
    chegar, coloque-o em ws/src/FAST_LIO e rode:

      colcon build --packages-select fast_lio

    Detalhes em GUIA-BASIC.md e README.md
EOF
