# Sobe o Nav2 (map_server, amcl, costmaps, planner_server, controller_server,
# bt_navigator, via nav2_bringup) e um RViz configurado para navegacao.
#
# Nao sobe o Gazebo de proposito, mesmo padrao do limo_slam: a simulacao roda
# em outro terminal (ros2 launch limo_car ackermann_gazebo.launch.py), o que
# permite reiniciar o Nav2 sem derrubar o mundo e o robo.

import os

from ament_index_python.packages import get_package_share_directory

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():

    pkg_share = get_package_share_directory('limo_nav2')
    bringup_share = get_package_share_directory('nav2_bringup')

    default_map = os.path.join(
        os.path.expanduser('~'), 'ws', 'maps', 'sala.yaml')
    default_params = os.path.join(pkg_share, 'config', 'nav2_params.yaml')
    default_rviz = os.path.join(pkg_share, 'rviz', 'nav2.rviz')

    map_yaml = LaunchConfiguration('map')
    params_file = LaunchConfiguration('params_file')
    use_sim_time = LaunchConfiguration('use_sim_time')
    open_rviz = LaunchConfiguration('rviz')

    declare_map = DeclareLaunchArgument(
        'map', default_value=default_map,
        description='Caminho completo do .yaml do mapa (gerado com '
                     'nav2_map_server map_saver_cli -- ver GUIA-BASIC.md, secao 6)')

    declare_params_file = DeclareLaunchArgument(
        'params_file', default_value=default_params,
        description='Arquivo de parametros do Nav2')

    declare_use_sim_time = DeclareLaunchArgument(
        'use_sim_time', default_value='true',
        description='Usar o relogio da simulacao (/clock) em vez do relogio do sistema')

    declare_rviz = DeclareLaunchArgument(
        'rviz', default_value='true',
        description='Abrir o RViz junto com o Nav2')

    nav2_bringup = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(bringup_share, 'launch', 'bringup_launch.py')),
        launch_arguments={
            'map': map_yaml,
            'params_file': params_file,
            'use_sim_time': use_sim_time,
            'slam': 'False',
            'autostart': 'true',
        }.items(),
    )

    rviz_node = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz2_nav2',
        output='screen',
        arguments=['-d', default_rviz],
        parameters=[{'use_sim_time': use_sim_time}],
        condition=IfCondition(open_rviz),
    )

    return LaunchDescription([
        declare_map,
        declare_params_file,
        declare_use_sim_time,
        declare_rviz,
        nav2_bringup,
        rviz_node,
    ])
