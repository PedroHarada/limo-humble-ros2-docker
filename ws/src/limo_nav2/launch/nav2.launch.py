# Sobe o Nav2 (costmaps, planner_server, controller_server, bt_navigator, via
# nav2_bringup) e um RViz configurado para navegacao.
#
# Nao sobe o Gazebo de proposito, mesmo padrao do limo_slam: a simulacao roda
# em outro terminal (ros2 launch limo_car ackermann_gazebo.launch.py), o que
# permite reiniciar o Nav2 sem derrubar o mundo e o robo.
#
# localization_source escolhe de onde vem a localizacao:
#   amcl      -- comportamento historico: map_server + AMCL contra mapa salvo
#   fast_lio  -- nao sobe o AMCL; a cadeia map -> odom -> base_footprint vem do
#                FAST_LIO (que ainda nao esta no workspace -- ver README).
#                Neste modo o map_server continua subindo, porque o
#                static_layer do global_costmap depende do topico /map.

import os

from ament_index_python.packages import get_package_share_directory

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.conditions import IfCondition, UnlessCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PythonExpression
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
    localization_source = LaunchConfiguration('localization_source')

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

    declare_localization_source = DeclareLaunchArgument(
        'localization_source', default_value='amcl',
        choices=['amcl', 'fast_lio'],
        description="Fonte de localizacao: 'amcl' (mapa salvo) ou "
                    "'fast_lio' (TF publicada pelo FAST_LIO; sem AMCL)")

    is_fast_lio = PythonExpression(
        ["'", localization_source, "' == 'fast_lio'"])

    # ---- amcl: fluxo historico, inalterado -------------------------------
    nav2_amcl_bringup = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(bringup_share, 'launch', 'bringup_launch.py')),
        launch_arguments={
            'map': map_yaml,
            'params_file': params_file,
            'use_sim_time': use_sim_time,
            'slam': 'False',
            'autostart': 'true',
        }.items(),
        condition=UnlessCondition(is_fast_lio),
    )

    # ---- fast_lio: map_server (static_layer) + navegacao, sem AMCL --------
    # A localizacao (map -> odom -> base_footprint) deve ser publicada pelo
    # FAST_LIO. Os nomes de frame/topicos do FAST_LIO precisam ser conferidos
    # quando o pacote chegar -- ver a secao "Nav2 sem AMCL" do README.
    fast_lio_map_server = Node(
        package='nav2_map_server',
        executable='map_server',
        name='map_server',
        output='screen',
        parameters=[{
            'use_sim_time': use_sim_time,
            'yaml_filename': map_yaml,
        }],
        condition=IfCondition(is_fast_lio),
    )

    fast_lio_lifecycle_manager = Node(
        package='nav2_lifecycle_manager',
        executable='lifecycle_manager',
        name='lifecycle_manager_localization',
        output='screen',
        parameters=[{
            'use_sim_time': use_sim_time,
            'autostart': True,
            'node_names': ['map_server'],
        }],
        condition=IfCondition(is_fast_lio),
    )

    nav2_fast_lio_navigation = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(bringup_share, 'launch', 'navigation_launch.py')),
        launch_arguments={
            'use_sim_time': use_sim_time,
            'params_file': params_file,
            'autostart': 'true',
            'use_composition': 'False',
        }.items(),
        condition=IfCondition(is_fast_lio),
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
        declare_localization_source,
        nav2_amcl_bringup,
        fast_lio_map_server,
        fast_lio_lifecycle_manager,
        nav2_fast_lio_navigation,
        rviz_node,
    ])
