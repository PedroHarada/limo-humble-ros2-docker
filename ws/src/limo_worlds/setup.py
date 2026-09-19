import os
from glob import glob

from setuptools import setup

package_name = 'limo_worlds'


def _walk_data_files(root, dest_prefix):
    """Gera uma entrada de data_files por diretorio, preservando a arvore.

    O data_files do setuptools achata os arquivos dentro do destino, entao um
    diretorio recursivo precisa de uma entrada por pasta. E o caso de models/,
    que tem centenas de meshes em subpastas.
    """
    entries = []
    for dirpath, _dirnames, filenames in os.walk(root):
        if not filenames:
            continue
        entries.append((
            os.path.join(dest_prefix, dirpath),
            [os.path.join(dirpath, name) for name in filenames],
        ))
    return entries


setup(
    name=package_name,
    version='1.0.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'), glob('launch/*.launch.py')),
        (os.path.join('share', package_name, 'config'), glob('config/*.yaml')),
        (os.path.join('share', package_name, 'worlds'),
         glob('worlds/*.model') + glob('worlds/*.sdf')),
    ] + _walk_data_files('models', os.path.join('share', package_name)),
    install_requires=['setuptools'],
    tests_require=['pytest'],
    zip_safe=True,
    maintainer='Pedro Harada',
    maintainer_email='pedroyujiharada@gmail.com',
    description='Mundos do Gazebo com obstáculos móveis e floresta, para testar replanejamento do Nav2',
    license='Apache-2.0',
    entry_points={
        'console_scripts': [
            'obstacle_mover = limo_worlds.obstacle_mover:main',
        ],
    },
)
