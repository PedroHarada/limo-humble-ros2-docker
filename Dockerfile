FROM osrf/ros:humble-desktop-full

ARG DEBIAN_FRONTEND=noninteractive

# Pacotes ROS 2 Humble (Gazebo Classic, Nav2, SLAM) + ferramentas de build/dev
RUN apt-get update && apt-get install -y --no-install-recommends \
      ros-humble-gazebo-ros-pkgs \
      ros-humble-gazebo-ros2-control \
      ros-humble-navigation2 \
      ros-humble-nav2-bringup \
      ros-humble-slam-toolbox \
      ros-humble-teleop-twist-keyboard \
      ros-humble-rqt-robot-steering \
      ros-humble-joint-state-publisher-gui \
      ros-humble-tf2-tools \
      ros-humble-xacro \
      python3-colcon-common-extensions \
      python3-rosdep \
      git \
      vim \
      tmux \
    && rm -rf /var/lib/apt/lists/*

# Dependencias de build do FAST_LIO (PCL, Eigen, glog) e do driver Livox
# (PCL, apr). O ros2_livox_simulation tambem precisa de PCL.
RUN apt-get update && apt-get install -y --no-install-recommends \
      cmake \
      libpcl-dev \
      libeigen3-dev \
      libgoogle-glog-dev \
      libfmt-dev \
      libapr1-dev \
      ros-humble-ament-cmake-auto \
      ros-humble-pcl-conversions \
      ros-humble-pcl-ros \
    && rm -rf /var/lib/apt/lists/*

# Livox-SDK2: o livox_ros_driver2 (que gera a mensagem CustomMsg consumida
# pelo FAST_LIO e pelo ros2_livox_simulation) linka contra esta SDK.
RUN git clone --depth 1 https://github.com/Livox-SDK/Livox-SDK2.git /tmp/Livox-SDK2 \
    && cmake -S /tmp/Livox-SDK2 -B /tmp/Livox-SDK2/build \
    && cmake --build /tmp/Livox-SDK2/build -j"$(nproc)" \
    && cmake --install /tmp/Livox-SDK2/build \
    && ldconfig \
    && rm -rf /tmp/Livox-SDK2

# Sophus da fonte: o FAST_LIO depende dele e nao ha pacote apt no Humble.
# SOPHUS_USE_BASIC_LOGGING evita a dependencia de fmt no uso que o FAST_LIO faz.
RUN git clone --depth 1 --branch 1.22.10 https://github.com/strasdat/Sophus.git /tmp/Sophus \
    && cmake -S /tmp/Sophus -B /tmp/Sophus/build -DSOPHUS_USE_BASIC_LOGGING=ON \
    && cmake --build /tmp/Sophus/build -j"$(nproc)" \
    && cmake --install /tmp/Sophus/build \
    && rm -rf /tmp/Sophus

# sudo em camada separada de proposito: nao invalida a camada de apt acima,
# que e a cara de reconstruir
RUN apt-get update && apt-get install -y --no-install-recommends sudo \
    && rm -rf /var/lib/apt/lists/*

# Usuario nao-root com o UID/GID do host. Duas razoes:
#  1. os arquivos que o colcon gera no bind mount de ./ws nascem do usuario do
#     host, nao do root -- sem precisar de sudo para limpar build/ install/ log/
#  2. o Xwayland autoriza por credencial do socket (SI:localuser:<uid>), entao
#     rodar como UID 1000 dispensa o xhost a cada login
ARG USERNAME=limo
ARG USER_UID=1000
ARG USER_GID=1000
RUN groupadd --gid ${USER_GID} ${USERNAME} \
    && useradd --uid ${USER_UID} --gid ${USER_GID} --create-home --shell /bin/bash ${USERNAME} \
    && echo "${USERNAME} ALL=(root) NOPASSWD:ALL" > /etc/sudoers.d/${USERNAME} \
    && chmod 0440 /etc/sudoers.d/${USERNAME}

USER ${USERNAME}
ENV HOME=/home/${USERNAME}

# Base de dados do rosdep (rosdep init ja vem feito na imagem osrf/ros).
# Roda como o usuario para o cache cair no HOME dele.
RUN rosdep update --rosdistro humble

# Source automatico do ROS e do overlay do workspace (condicional: o install/
# so existe depois do primeiro colcon build)
RUN echo 'source /opt/ros/humble/setup.bash' >> ${HOME}/.bashrc && \
    echo '[ -f ${HOME}/ws/install/setup.bash ] && source ${HOME}/ws/install/setup.bash' >> ${HOME}/.bashrc

# DISTRO_ROS=humble e lido pelo CMakeLists do livox_ros_driver2 para escolher a
# API de typesupport certa. Fica em defaults do colcon para que o
# "colcon build" documentado no GUIA continue funcionando sem flags extras.
RUN mkdir -p ${HOME}/.colcon && \
    printf 'build:\n  cmake-args:\n    - -DDISTRO_ROS=humble\n' \
      > ${HOME}/.colcon/defaults.yaml

WORKDIR /home/${USERNAME}/ws

CMD ["bash"]
