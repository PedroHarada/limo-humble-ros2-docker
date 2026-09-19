# Sobe o Gazebo com o mundo floresta (forest_diverse_10min.sdf) e faz spawn do
# LIMO ackermann nele, reaproveitando o ackermann_gazebo.launch.py do limo_car.
#
# Nao sobe Nav2 nem SLAM: mesmo padrao do limo_slam/limo_nav2, a simulacao roda
# num terminal e o stack de navegacao em outro.
#
# O mundo referencia model://mrs_gazebo_common_resources/models/grass_plane e
# model://<arvore> para os modelos do proprio limo_worlds. Como o clone do
# mrs_gazebo_common_resources e ROS 1 (catkin) e nao e compilado pelo colcon,
# o GAZEBO_MODEL_PATH e montado aqui apontando para os clones em ~/ws/src.

import os

from ament_index_python.packages import get_package_share_directory

from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    IncludeLaunchDescription,
    SetEnvironmentVariable,
)
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration


def generate_launch_description():
    pkg_share = get_package_share_directory('limo_worlds')
    limo_car_share = get_package_share_directory('limo_car')

    default_world = os.path.join(
        pkg_share, 'worlds', 'forest_diverse_10min.sdf')

    world_arg = DeclareLaunchArgument(
        name='world', default_value=default_world,
        description='Caminho absoluto do .sdf do mundo floresta')

    ws_src = os.path.join(os.path.expanduser('~'), 'ws', 'src')
    # Acrescenta aos caminhos que ja existirem no ambiente (ex.: os que o
    # gazebo_ros_paths_plugin/colcon registram para os proprios pacotes ROS,
    # de onde vem os meshes/materiais do LIMO) em vez de substitui-los -- um
    # SetEnvironmentVariable sem isso apaga esses caminhos e deixa o robo sem
    # material (aparece todo preto).
    existing_model_path = os.environ.get('GAZEBO_MODEL_PATH', '')
    gazebo_model_path = os.pathsep.join(filter(None, [
        os.path.join(pkg_share, 'models'),
        os.path.join(pkg_share, 'models', 'forest-gen-models'),
        os.path.join(ws_src, 'mrs_gazebo_common_resources', 'models'),
        ws_src,
        '/usr/share/gazebo-11/models',
        os.path.join(os.path.expanduser('~'), '.gazebo', 'models'),
        existing_model_path,
    ]))

    set_gazebo_model_path = SetEnvironmentVariable(
        'GAZEBO_MODEL_PATH', gazebo_model_path)

    ackermann_gazebo = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(limo_car_share, 'launch', 'ackermann_gazebo.launch.py')),
        launch_arguments={'world': LaunchConfiguration('world')}.items(),
    )

    return LaunchDescription([
        world_arg,
        set_gazebo_model_path,
        ackermann_gazebo,
    ])
