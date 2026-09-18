import os

from ament_index_python.packages import get_package_share_directory

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration

from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    pkg_path = get_package_share_directory('limo_worlds')
    default_obstacles = os.path.join(pkg_path, 'config', 'obstacles.yaml')

    obstacles_arg = DeclareLaunchArgument(
        name='obstacles_file', default_value=default_obstacles,
        description='YAML com as trajetórias dos obstáculos móveis')
    use_sim_time_arg = DeclareLaunchArgument(
        name='use_sim_time', default_value='true',
        description='Seguir o /clock do Gazebo em vez do relógio de parede')

    mover = Node(
        package='limo_worlds',
        executable='obstacle_mover',
        name='obstacle_mover',
        output='screen',
        parameters=[{
            'obstacles_file': LaunchConfiguration('obstacles_file'),
            'use_sim_time': ParameterValue(
                LaunchConfiguration('use_sim_time'), value_type=bool),
        }],
    )

    return LaunchDescription([
        obstacles_arg,
        use_sim_time_arg,
        mover,
    ])
