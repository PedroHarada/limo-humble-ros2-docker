#!/usr/bin/env bash
#
# Prepara o ambiente para ESTA máquina:
#   1. gera o .env com UID/GID do usuário e os GIDs de video e render
#   2. garante que o arquivo de autoridade do X exista
#   3. clona o limo_ros2 e aplica as correções de patches/
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

    Detalhes em GUIA-BASIC.md
EOF
