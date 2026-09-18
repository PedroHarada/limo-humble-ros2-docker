# Basic usage guide

*[Versão em português](GUIA-BASIC.md)*

How to bring the environment up and operate the tools inside the container. For
the design decisions and the fixes applied to `limo_ros2`, see the
[README.en.md](README.en.md).

---

## 1. First time

Once, on the host:

```bash
cd ~/limo-docker
./setup.sh
docker compose build
```

`setup.sh` does three things, and is idempotent (safe to re-run):

1. Detects your user's UID/GID and this machine's `video` and `render` group
   GIDs, writing them to `.env`. These numbers vary across distributions, and
   they are what gives the container GPU access and correct file ownership.
2. Makes sure the X authority file exists (using the correct `$XAUTHORITY`,
   which on GNOME/Wayland is not `~/.Xauthority`).
3. Clones `limo_ros2` into `ws/src/` and applies the fixes from
   `patches/limo_ros2-fixes.patch`. **Without this step there is nothing to
   build** — this repository does not version the robot's source, only the patch.

Run `setup.sh` from a terminal in your graphical session, otherwise it cannot
find out the `DISPLAY`.

`docker compose build` takes a few minutes (the `osrf/ros:humble-desktop-full`
base image is several GB). Afterwards, with the container running, the workspace
has to be compiled once — see section 3.

## 2. Daily routine

```bash
cd ~/limo-docker
docker compose up -d              # start the container in the background
docker compose exec limo bash     # open a shell inside it
```

To open **more terminals** in the same container, repeat `docker compose exec
limo bash` in another host window. You will want at least three: one for the
simulation, one for control, one for inspecting topics.

When done:

```bash
docker compose down
```

No `xhost` needed — the container runs with your own UID and Xwayland already
authorizes it. The reasoning is in the README.

## 3. Building the workspace

Inside the container:

```bash
cd ~/ws
sudo apt-get update                              # only the first time after a build
rosdep install --from-paths src --ignore-src -r -y
colcon build --symlink-install
source install/setup.bash
```

After the first build, the `source` happens automatically in every new shell
(it is in `.bashrc`).

**When a rebuild is actually needed:** only when touching C++ code or adding
packages. Thanks to `--symlink-install`, editing launch files, `.xacro`, `.rviz`
or world files **on the host** already takes effect inside the container — just
relaunch.

## 4. Running the simulation

```bash
ros2 launch limo_car ackermann_gazebo.launch.py
```

This starts three things: Gazebo with the 10x10 m room, the LIMO at the origin,
and RViz preconfigured with the robot model, the laser and the camera image.

Leave that terminal busy with the simulation. `Ctrl+C` shuts everything down.

To load a different world, use `world:=`, with either the name of a file inside
`limo_car/worlds/` or an absolute path:

```bash
ros2 launch limo_car ackermann_gazebo.launch.py \
  world:=$(ros2 pkg prefix limo_worlds)/share/limo_worlds/worlds/dynamic_world.model
```

That is the world with a moving obstacle — see section 8.

## 5. Driving the robot

### Option A: sliders (easiest)

In another container terminal:

```bash
ros2 run rqt_robot_steering rqt_robot_steering
```

1. In the text field at the top, type `/cmd_vel` and press Enter (it sometimes
   comes prefilled with a wrong value, or empty).
2. The **vertical** slider is linear velocity (m/s). The **horizontal** one is
   angular velocity (rad/s).
3. Start with modest maximums: `0.3` linear and `0.5` angular.
4. The big **Stop** button zeroes both. Use it before closing the window —
   otherwise the last `cmd_vel` stays in effect and the robot keeps moving.

### Option B: keyboard

```bash
ros2 run teleop_twist_keyboard teleop_twist_keyboard
```

The keys are hardcoded in the package (there is no configuration file):

```
u    i    o        i = forward            k = stop
j    k    l        , = reverse            j / l = turn in place
m    ,    .        u, o, m, . = arcs
```

Speed: `q`/`z` changes both, `w`/`x` linear only, `e`/`c` angular only.

**The terminal must have focus.** If you click on the Gazebo window, the robot
stops responding to keystrokes.

### An ackermann quirk

With linear velocity at **zero**, moving the angular does nothing. A car with
steering cannot rotate in place: the wheels turn, but it does not move. Give it
linear velocity first, then steer.

## 6. Mapping the room with SLAM

The `limo_slam` package ships `slam_toolbox` already configured for this robot.
It belongs to your workspace, not to AgileX's upstream.

Build it once (it is a new package, so `--symlink-install` does not spare you
the build):

```bash
cd ~/ws
colcon build --symlink-install --packages-select limo_slam
source install/setup.bash
```

With the **simulation already running** in another terminal:

```bash
ros2 launch limo_slam slam.launch.py
```

This starts `slam_toolbox` and a **second** RViz window, with Fixed Frame set to
`map` and the map display on. The RViz that came with the simulation stays on
`base_footprint` and does not show the map — feel free to minimize it.

Accepted arguments:

| Argument | Default | What it does |
|---|---|---|
| `rviz:=false` | `true` | start SLAM only, without the second RViz |
| `use_sim_time:=false` | `true` | only makes sense with a real robot |
| `params_file:=/path/x.yaml` | the package's | try parameters without editing the original |

Check that it is up:

```bash
ros2 topic hz /map                    # publishes every ~5 s
ros2 run tf2_ros tf2_echo map odom    # the link slam_toolbox adds
```

Now drive (section 5) and watch the map grow in RViz.

### How to drive for a good map

**The lidar sees 240°, not 360°.** In `sensor.xacro` the field of view runs from
-2.09 to +2.09 rad: the LIMO sees ahead and to the sides, and is blind behind.
Driving only forward leaves holes — go around the room in both directions.

**Go slow.** The scan matcher matches consecutive scans; high speed with an 8 Hz
lidar produces large jumps between readings, and the map comes out skewed.

**Standing still, nothing happens.** With `minimum_travel_distance: 0.1`, a new
scan is only processed every 10 cm travelled. That is deliberate: processing
scans while the robot is parked only piles up noise.

### Saving the map

```bash
mkdir -p ~/ws/maps
ros2 run nav2_map_server map_saver_cli -f ~/ws/maps/sala
```

This produces `sala.pgm` (the image) and `sala.yaml` (resolution, origin and
thresholds). Since `~/ws` is the bind mount, both show up on the host under
`~/limo-docker/ws/maps/`, owned by your user. They are Nav2's input later on.

### If the map comes out bad

| Symptom | Likely cause | What to do |
|---|---|---|
| Empty map, nothing shows | SLAM is not getting `/scan`, or there is no TF | `ros2 topic hz /scan` and `ros2 run tf2_ros tf2_echo map odom` |
| Duplicated or "ghost" walls | odometry slipping, scan matcher losing the match | drive slower; revisit an already mapped stretch to trigger loop closure |
| Map only grows in front of the robot | the 240° field of view | cover the room in both directions |
| Map does not update while driving | inconsistent `use_sim_time` across nodes | all of them need `use_sim_time: true`; check with `ros2 param get /slam_toolbox use_sim_time` |

## 7. Navigating with Nav2

The `limo_nav2` package brings Nav2 configured for this robot: AMCL for
localization against a saved map, 2D costmaps built from `/scan`, and the
`RegulatedPurePursuitController` in place of the default `DWB` — `DWB`
assumes differential drive and would try to rotate the robot in place, which
the LIMO (Ackermann) cannot do.

**Prerequisite:** a saved map (section 6). The launch defaults to
`~/ws/maps/sala.yaml`.

Build it once:

```bash
cd ~/ws
colcon build --symlink-install --packages-select limo_nav2
source install/setup.bash
```

With the **simulation already running** in another terminal (relaunch it from
scratch if the robot is no longer at the origin — the map was saved with the
robot starting at (0,0,0), and Nav2 assumes that same initial pose):

```bash
ros2 launch limo_nav2 nav2.launch.py
```

This brings up `map_server`, `amcl`, the local and global costmaps,
`planner_server`, `controller_server`, `bt_navigator` (via `nav2_bringup`),
and an RViz with the **Nav2 Goal** tool. Unlike `slam.launch.py`, the robot is
already localized on startup — no manual "2D Pose Estimate" needed.

Accepted arguments:

| Argument | Default | What it is for |
|---|---|---|
| `map:=/path/other.yaml` | `~/ws/maps/sala.yaml` | use a different saved map |
| `params_file:=/path/x.yaml` | the package's own | test parameters without editing the original |
| `rviz:=false` | `true` | bring up only Nav2, without opening RViz |
| `use_sim_time:=false` | `true` | would only make sense with a real robot |

To send the robot to a destination: click **Nav2 Goal** in the RViz toolbar,
then click and drag on the map (dragging sets the final orientation). Check
that it is up:

```bash
ros2 topic list | grep navigate_to_pose    # the bt_navigator action
ros2 lifecycle get /amcl                   # should answer "active"
```

### If the robot does not move

| Symptom | Likely cause | What to do |
|---|---|---|
| `RegulatedPurePursuitController detected collision ahead!` looping, no movement | the map has "ghost walls" near the robot (rushed or incomplete mapping) | redo the mapping (section 6), driving slower and covering the whole room |
| `/amcl` topics never show the expected `active` state | the fixed initial pose (0,0,0) does not match the robot's real pose | relaunch the simulation from scratch (`ros2 launch limo_car ackermann_gazebo.launch.py`) before Nav2, so the robot returns to the origin |
| Goal accepted but cancels right after | goal outside the mapped area, or inside an inflated obstacle | pick a more central point on the map, away from the walls |

## 8. Moving obstacles

The `limo_worlds` package ships the same room as always, plus a box that
crosses it from side to side and back, in a loop. It is there to watch Nav2
react to something that is not in the saved map.

Two pieces: the world (loaded by Gazebo) and the node that moves the box.
Without the node, the box just sits where it was spawned.

Build it once:

```bash
cd ~/ws
colcon build --symlink-install --packages-select limo_worlds
source install/setup.bash
```

Terminal 1, the simulation with the dynamic world:

```bash
ros2 launch limo_car ackermann_gazebo.launch.py \
  world:=$(ros2 pkg prefix limo_worlds)/share/limo_worlds/worlds/dynamic_world.model
```

Terminal 2, the node that animates the obstacles:

```bash
ros2 launch limo_worlds dynamic_obstacles.launch.py
```

The red box should start running along the `y = -2.5` corridor. To confirm the
lidar sees it, watch `/scan` in RViz: the points track the box.

### Building your own scenarios

The trajectory lives in `ws/src/limo_worlds/config/obstacles.yaml`, as
linearly interpolated waypoints:

```yaml
obstacles:
  - name: crossing_box      # must exist as a <model> in the loaded world
    z: 0.4                  # height of the model's center
    loop: true              # restart when the trajectory ends
    waypoints:
      - {time: 0.0, x: -4.0, y: -2.5, yaw: 0.0}
      - {time: 10.0, x: 4.0, y: -2.5, yaw: 0.0}
      - {time: 20.0, x: -4.0, y: -2.5, yaw: 0.0}
```

For a new obstacle: copy the `<model name="crossing_box">` block in
`worlds/dynamic_world.model`, give it another name, and add an entry of the
same name to the YAML. Use a different YAML without rebuilding with
`ros2 launch limo_worlds dynamic_obstacles.launch.py obstacles_file:=/path/mine.yaml`.

Two rules about the world, valid for any moving obstacle you create:

- Use `<model>`, **never `<actor>`**. Gazebo Classic does not hand actor
  collisions to ray sensors: the obstacle moves on screen and the lidar does
  not see it.
- The link needs `<kinematic>true</kinematic>` and `<gravity>false</gravity>`,
  otherwise physics fights the node over the model's pose.

| Symptom | Likely cause | What to do |
|---|---|---|
| The obstacle does not move | the node did not start, or the name in the YAML does not match the `<model>` in the world | check terminal 2's log and the names |
| `/gazebo/set_entity_state unavailable` | the loaded world is not `dynamic_world.model` (only it declares the state plugin) | check `world:=` in terminal 1 |
| The robot drives through the obstacle | the obstacle is an `<actor>`, or the link has no `<collision>` | use a `<model>` with collision, as above |

## 9. Inspecting what is going on

| Goal | Command |
|---|---|
| List active nodes | `ros2 node list` |
| List topics | `ros2 topic list` |
| Watch commands being sent | `ros2 topic echo /cmd_vel` |
| Watch odometry | `ros2 topic echo /odom --field pose.pose.position` |
| Check the laser header | `ros2 topic echo /scan --once --field header` |
| Topic rate | `ros2 topic hz /scan` |
| Check one transform | `ros2 run tf2_ros tf2_echo base_footprint laser_link` |
| Full TF tree as PDF | `ros2 run tf2_tools view_frames` |
| Node and topic graph | `rqt_graph` |

Main simulation topics:

| Topic | Contents |
|---|---|
| `/cmd_vel` | velocity command (input) |
| `/odom` | odometry from the ackermann plugin |
| `/scan` | 2D lidar, 720 samples, 8 m range |
| `/imu` | IMU |
| `/depth_camera/image_raw` | depth camera |
| `/tf`, `/tf_static` | transform tree |

## 10. Editing the scene

The world lives in `ws/src/limo_ros2/limo_car/worlds/empty_world.model` and can
be edited on the host with any editor. It contains a closed 10x10 m room, two
boxes and a cylinder.

For one-off obstacles without editing files: the **Insert** tab in Gazebo, pick
a shape and click on the ground. They disappear when Gazebo closes.

For a file edit to take effect, relaunch — the world is only read when
`gzserver` starts.

## 11. Common problems

| Symptom | Likely cause | What to do |
|---|---|---|
| `cannot open display` | `DISPLAY` not exported in the host terminal before `up` | run `echo $DISPLAY` on the host; if empty, reopen the terminal and redo `docker compose up -d` |
| Robot ignores the keyboard | teleop terminal lost focus | click on the teleop terminal |
| Robot will not turn | linear velocity is zero | give it linear velocity before steering |
| Robot keeps driving by itself | last `cmd_vel` still in effect | `Stop` in rqt, or `k` in teleop |
| RViz 3D view empty | Fixed Frame has no TF | `ros2 run tf2_ros tf2_echo base_footprint base_link` |
| Gazebo black or frozen | GPU rendering | try `LIBGL_ALWAYS_SOFTWARE=1` under `environment:` in the compose file (much slower) |
| `groups: cannot find name for group ID 992` | the `render` group has no name inside the container | cosmetic, ignore |
| ALSA error messages | no sound card in the container | cosmetic, ignore |

## 12. Where things live

| On the host | In the container |
|---|---|
| `~/limo-docker/ws/` | `/home/limo/ws` |
| `~/limo-docker/ws/src/limo_ros2/` | `/home/limo/ws/src/limo_ros2` |

The workspace is a bind mount: what you edit on the host takes effect in the
container immediately, and files produced by the build belong to your user.
