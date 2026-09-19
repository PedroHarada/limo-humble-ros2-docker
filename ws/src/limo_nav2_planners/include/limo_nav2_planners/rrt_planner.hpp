#ifndef LIMO_NAV2_PLANNERS__RRT_PLANNER_HPP_
#define LIMO_NAV2_PLANNERS__RRT_PLANNER_HPP_

#include <memory>
#include <string>

#include "nav2_core/global_planner.hpp"
#include "nav2_costmap_2d/costmap_2d.hpp"
#include "nav2_costmap_2d/costmap_2d_ros.hpp"
#include "nav2_util/lifecycle_node.hpp"
#include "rclcpp/rclcpp.hpp"
#include "tf2_ros/buffer.h"

namespace limo_nav2_planners
{

/**
 * @brief Esqueleto de um planner global RRT para o Nav2.
 *
 * A interface nav2_core::GlobalPlanner já está implementada (configure,
 * cleanup, activate, deactivate, createPlan). O algoritmo em si é o único
 * ponto que falta: veja o TODO em createPlan() no .cpp.
 */
class RRTPlanner : public nav2_core::GlobalPlanner
{
public:
  RRTPlanner() = default;
  ~RRTPlanner() override = default;

  void configure(
    const rclcpp_lifecycle::LifecycleNode::WeakPtr & parent,
    std::string name, std::shared_ptr<tf2_ros::Buffer> tf,
    std::shared_ptr<nav2_costmap_2d::Costmap2DROS> costmap_ros) override;

  void cleanup() override;
  void activate() override;
  void deactivate() override;

  nav_msgs::msg::Path createPlan(
    const geometry_msgs::msg::PoseStamped & start,
    const geometry_msgs::msg::PoseStamped & goal) override;

protected:
  rclcpp_lifecycle::LifecycleNode::SharedPtr node_;
  std::shared_ptr<tf2_ros::Buffer> tf_;
  std::shared_ptr<nav2_costmap_2d::Costmap2DROS> costmap_ros_;
  nav2_costmap_2d::Costmap2D * costmap_{nullptr};
  std::string name_;
  bool active_{false};
  double tolerance_{0.25};
  int max_iterations_{10000};
};

}  // namespace limo_nav2_planners

#endif  // LIMO_NAV2_PLANNERS__RRT_PLANNER_HPP_
