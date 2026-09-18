import os
from glob import glob

from setuptools import setup

package_name = 'limo_worlds'

setup(
    name=package_name,
    version='1.0.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'), glob('launch/*.launch.py')),
        (os.path.join('share', package_name, 'config'), glob('config/*.yaml')),
        (os.path.join('share', package_name, 'worlds'), glob('worlds/*.model')),
    ],
    install_requires=['setuptools'],
    tests_require=['pytest'],
    zip_safe=True,
    maintainer='Pedro Harada',
    maintainer_email='pedroyujiharada@gmail.com',
    description='Mundos do Gazebo com obstáculos móveis, para testar replanejamento do Nav2',
    license='Apache-2.0',
    entry_points={
        'console_scripts': [
            'obstacle_mover = limo_worlds.obstacle_mover:main',
        ],
    },
)
