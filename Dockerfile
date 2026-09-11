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

WORKDIR /home/${USERNAME}/ws

CMD ["bash"]
