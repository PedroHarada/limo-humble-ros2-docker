cmake_minimum_required(VERSION 3.8)
project(limo_nav2_planners)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)
find_package(nav2_core REQUIRED)
find_package(nav2_costmap_2d REQUIRED)
find_package(nav2_util REQUIRED)
find_package(pluginlib REQUIRED)
find_package(rclcpp REQUIRED)
find_package(rclcpp_lifecycle REQUIRED)
find_package(nav_msgs REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(tf2_ros REQUIRED)

add_library(${PROJECT_NAME} SHARED
  src/astar_planner.cpp
  src/rrt_planner.cpp
)

target_include_directories(${PROJECT_NAME} PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>
)

ament_target_dependencies(${PROJECT_NAME}
  nav2_core
  nav2_costmap_2d
  nav2_util
  pluginlib
  rclcpp
  rclcpp_lifecycle
  nav_msgs
  geometry_msgs
  tf2_ros
)

install(TARGETS ${PROJECT_NAME}
  ARCHIVE DESTINATION lib
  LIBRARY DESTINATION lib
  RUNTIME DESTINATION bin
)

install(DIRECTORY include/
  DESTINATION include
)

# Registra as classes no pluginlib, no grupo nav2_core::GlobalPlanner, para
# que o planner_server as encontre pelo nome ("limo_nav2_planners/AStarPlanner")
pluginlib_export_plugin_description_file(nav2_core plugin.xml)

ament_export_include_directories(include)
ament_export_libraries(${PROJECT_NAME})
ament_export_dependencies(
  nav2_core
  nav2_costmap_2d
  nav2_util
  pluginlib
  rclcpp
  rclcpp_lifecycle
  nav_msgs
  geometry_msgs
  tf2_ros
)

ament_package()
