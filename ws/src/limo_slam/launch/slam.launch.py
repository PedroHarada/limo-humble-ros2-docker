# Sobe o slam_toolbox (online assincrono) e o RViz configurado para SLAM.
#
# Nao sobe o Gazebo de proposito: a simulacao roda em outro terminal
# (ros2 launch limo_car ackermann_gazebo.launch.py), o que permite
# reiniciar o SLAM sem derrubar o mundo e o robo.

import os

from ament_index_python.packages import get_package_share_directory

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():

    pkg_share = get_package_share_directory('limo_slam')
    default_params = os.path.join(
        pkg_share, 'config', 'mapper_params_online_async.yaml')
    default_rviz = os.path.join(pkg_share, 'rviz', 'slam.rviz')

    use_sim_time = LaunchConfiguration('use_sim_time')
    params_file = LaunchConfiguration('params_file')
    open_rviz = LaunchConfiguration('rviz')

    declare_use_sim_time = DeclareLaunchArgument(
        'use_sim_time', default_value='true',
        description='Usar o relogio da simulacao (/clock) em vez do relogio do sistema')

    declare_params_file = DeclareLaunchArgument(
        'params_file', default_value=default_params,
        description='Arquivo de parametros do slam_toolbox')

    declare_rviz = DeclareLaunchArgument(
        'rviz', default_value='true',
        description='Abrir o RViz junto com o SLAM')

    slam_node = Node(
        package='slam_toolbox',
        executable='async_slam_toolbox_node',
        name='slam_toolbox',
        output='screen',
        parameters=[
            params_file,
            {'use_sim_time': use_sim_time},
        ],
    )

    rviz_node = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz2_slam',
        output='screen',
        arguments=['-d', default_rviz],
        parameters=[{'use_sim_time': use_sim_time}],
        condition=IfCondition(open_rviz),
    )

    return LaunchDescription([
        declare_use_sim_time,
        declare_params_file,
        declare_rviz,
        slam_node,
        rviz_node,
    ])
