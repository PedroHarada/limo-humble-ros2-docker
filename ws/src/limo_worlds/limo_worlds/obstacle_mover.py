"""Move obstáculos do Gazebo ao longo de trajetórias lidas de um YAML.

O Gazebo Classic ignora <actor> nos sensores de raio, então os obstáculos são
modelos comuns (kinematic) e quem os anima é este nó, via o serviço
/gazebo/set_entity_state do plugin libgazebo_ros_state.so.
"""

import math

import rclpy
import yaml
from gazebo_msgs.srv import SetEntityState
from rclpy.node import Node

from limo_worlds.trajectory import pose_at


def load_obstacles(path):
    with open(path) as handle:
        data = yaml.safe_load(handle)
    obstacles = data['obstacles']
    for obstacle in obstacles:
        for waypoint in obstacle['waypoints']:
            waypoint.setdefault('yaw', 0.0)
    return obstacles


class ObstacleMover(Node):
    def __init__(self):
        super().__init__('obstacle_mover')
        self.declare_parameter('obstacles_file', '')
        self.declare_parameter('update_rate', 30.0)

        path = self.get_parameter('obstacles_file').value
        if not path:
            raise RuntimeError('parâmetro obstacles_file não informado')
        self.obstacles = load_obstacles(path)
        self.get_logger().info(
            f'{len(self.obstacles)} obstáculo(s) carregado(s) de {path}')

        self.client = self.create_client(SetEntityState, '/gazebo/set_entity_state')
        while not self.client.wait_for_service(timeout_sec=5.0):
            self.get_logger().warn(
                '/gazebo/set_entity_state indisponível; o mundo carregou o '
                'plugin libgazebo_ros_state.so?')

        self.pending = set()
        self.start = None
        rate = self.get_parameter('update_rate').value
        self.create_timer(1.0 / rate, self.tick)

    def tick(self):
        now = self.get_clock().now().nanoseconds * 1e-9
        if self.start is None:
            self.start = now
        elapsed = now - self.start

        for obstacle in self.obstacles:
            x, y, yaw = pose_at(
                obstacle['waypoints'], elapsed, obstacle.get('loop', True))
            request = SetEntityState.Request()
            request.state.name = obstacle['name']
            request.state.reference_frame = 'world'
            request.state.pose.position.x = x
            request.state.pose.position.y = y
            request.state.pose.position.z = float(obstacle.get('z', 0.0))
            request.state.pose.orientation.z = math.sin(yaw / 2.0)
            request.state.pose.orientation.w = math.cos(yaw / 2.0)
            future = self.client.call_async(request)
            self.pending.add(future)
            future.add_done_callback(self.pending.discard)


def main():
    rclpy.init()
    node = ObstacleMover()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    rclpy.shutdown()
