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

## 6. Inspecting what is going on

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

## 7. Editing the scene

The world lives in `ws/src/limo_ros2/limo_car/worlds/empty_world.model` and can
be edited on the host with any editor. It contains a closed 10x10 m room, two
boxes and a cylinder.

For one-off obstacles without editing files: the **Insert** tab in Gazebo, pick
a shape and click on the ground. They disappear when Gazebo closes.

For a file edit to take effect, relaunch — the world is only read when
`gzserver` starts.

## 8. Common problems

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

## 9. Where things live

| On the host | In the container |
|---|---|
| `~/limo-docker/ws/` | `/home/limo/ws` |
| `~/limo-docker/ws/src/limo_ros2/` | `/home/limo/ws/src/limo_ros2` |

The workspace is a bind mount: what you edit on the host takes effect in the
container immediately, and files produced by the build belong to your user.
