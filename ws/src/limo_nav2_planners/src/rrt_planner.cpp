#include "limo_nav2_planners/rrt_planner.hpp"

#include <string>

#include "nav2_util/node_utils.hpp"

namespace limo_nav2_planners
{

void RRTPlanner::configure(
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
  nav2_util::declare_parameter_if_not_declared(
    node_, name_ + ".max_iterations", rclcpp::ParameterValue(10000));
  tolerance_ = node_->get_parameter(name_ + ".tolerance").as_double();
  max_iterations_ = node_->get_parameter(name_ + ".max_iterations").as_int();

  RCLCPP_INFO(
    node_->get_logger(),
    "RRTPlanner \"%s\" configurado (esqueleto; createPlan ainda não planeja)",
    name_.c_str());
}

void RRTPlanner::cleanup()
{
  RCLCPP_INFO(node_->get_logger(), "Limpando o RRTPlanner \"%s\"", name_.c_str());
}

void RRTPlanner::activate()
{
  active_ = true;
  RCLCPP_INFO(node_->get_logger(), "Ativando o RRTPlanner \"%s\"", name_.c_str());
}

void RRTPlanner::deactivate()
{
  active_ = false;
  RCLCPP_INFO(node_->get_logger(), "Desativando o RRTPlanner \"%s\"", name_.c_str());
}

nav_msgs::msg::Path RRTPlanner::createPlan(
  const geometry_msgs::msg::PoseStamped & start,
  const geometry_msgs::msg::PoseStamped & goal)
{
  nav_msgs::msg::Path path;
  path.header.frame_id = costmap_ros_->getGlobalFrameID();
  path.header.stamp = node_->now();

  unsigned int mx = 0;
  unsigned int my = 0;
  if (!costmap_->worldToMap(start.pose.position.x, start.pose.position.y, mx, my)) {
    RCLCPP_WARN(node_->get_logger(), "RRTPlanner: start fora do costmap");
    return path;
  }

  // TODO(usuario): implementar RRT sobre costmap_ (costmap_->getCharMap()).
  // Sugestao de passos:
  //   1. worldToMap de start e goal (o de start ja esta acima);
  //   2. amostrar configuracoes aleatorias no costmap, rejeitando celulas
  //      letais/desconhecidas e checando colisao com getCost();
  //   3. conectar a amostra ao no mais proximo e checar o segmento;
  //   4. parar ao alcancar o goal (ou max_iterations_) e reconstruir o caminho;
  //   5. converter as celulas com mapToWorld e preencher path.poses.
  RCLCPP_WARN(
    node_->get_logger(),
    "RRTPlanner::createPlan ainda não está implementado; devolvendo caminho vazio");

  (void)goal;
  (void)max_iterations_;
  return path;
}

}  // namespace limo_nav2_planners

#include "pluginlib/class_list_macros.hpp"
PLUGINLIB_EXPORT_CLASS(limo_nav2_planners::RRTPlanner, nav2_core::GlobalPlanner)
