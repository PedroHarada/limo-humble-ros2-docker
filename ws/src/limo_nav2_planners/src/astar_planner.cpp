#include "limo_nav2_planners/astar_planner.hpp"

#include <string>

#include "nav2_util/node_utils.hpp"

namespace limo_nav2_planners
{

void AStarPlanner::configure(
  const rclcpp_lifecycle::LifecycleNode::WeakPtr & parent,
  std::string name, std::shared_ptr<tf2_ros::Buffer> tf,
  std::shared_ptr<nav2_costmap_2d::Costmap2DROS> costmap_ros)
{
  node_ = parent.lock();
  name_ = name;
  tf_ = tf;
  costmap_ros_ = costmap_ros;
  costmap_ = costmap_ros_->getCostmap();

  nav2_util::declare_parameter_if_not_declared(
    node_, name_ + ".tolerance", rclcpp::ParameterValue(0.25));
  tolerance_ = node_->get_parameter(name_ + ".tolerance").as_double();

  RCLCPP_INFO(
    node_->get_logger(),
    "AStarPlanner \"%s\" configurado (esqueleto; createPlan ainda não planeja)",
    name_.c_str());
}

void AStarPlanner::cleanup()
{
  RCLCPP_INFO(node_->get_logger(), "Limpando o AStarPlanner \"%s\"", name_.c_str());
}

void AStarPlanner::activate()
{
  active_ = true;
  RCLCPP_INFO(node_->get_logger(), "Ativando o AStarPlanner \"%s\"", name_.c_str());
}

void AStarPlanner::deactivate()
{
  active_ = false;
  RCLCPP_INFO(node_->get_logger(), "Desativando o AStarPlanner \"%s\"", name_.c_str());
}

nav_msgs::msg::Path AStarPlanner::createPlan(
  const geometry_msgs::msg::PoseStamped & start,
  const geometry_msgs::msg::PoseStamped & goal)
{
  nav_msgs::msg::Path path;
  path.header.frame_id = costmap_ros_->getGlobalFrameID();
  path.header.stamp = node_->now();

  unsigned int mx = 0;
  unsigned int my = 0;
  if (!costmap_->worldToMap(start.pose.position.x, start.pose.position.y, mx, my)) {
    RCLCPP_WARN(node_->get_logger(), "AStarPlanner: start fora do costmap");
    return path;
  }

  // TODO(usuario): implementar A* sobre costmap_ (costmap_->getCharMap()).
  // Sugestao de passos:
  //   1. worldToMap de start e goal (o de start ja esta acima);
  //   2. busca A* no grid usando getCost() como custo de celula;
  //   3. reconstruir o caminho e converter cada celula com mapToWorld;
  //   4. preencher path.poses com orientacoes coerentes com o yaw do trajeto.
  RCLCPP_WARN(
    node_->get_logger(),
    "AStarPlanner::createPlan ainda não está implementado; devolvendo caminho vazio");

  (void)goal;
  return path;
}

}  // namespace limo_nav2_planners

#include "pluginlib/class_list_macros.hpp"
PLUGINLIB_EXPORT_CLASS(limo_nav2_planners::AStarPlanner, nav2_core::GlobalPlanner)
