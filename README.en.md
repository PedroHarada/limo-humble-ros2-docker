# LIMO (AgileX) — Docker simulation

*[Versão em português](README.md)*

Simulation environment for the LIMO robot with **ROS 2 Humble**, **Gazebo
Classic** and **Nav2**, isolated in a Docker container, with graphics
acceleration on the integrated GPU (Mesa).

This document records **what was done, how and why**. For day-to-day operation,
see [GUIA-BASIC.en.md](GUIA-BASIC.en.md).

## Current state

Validated end to end: the LIMO shows up in Gazebo, RViz renders the model and
the laser, the robot responds to `/cmd_vel`, odometry accumulates and the TF
tree is connected. Gazebo runs at Real Time Factor 1.00 on the integrated GPU.

`slam_toolbox` is validated as well: driving the robot around the room builds
the map in RViz, with the walls and the three obstacles carved out.

Nav2 is validated end to end too: with a saved map and the robot at the
origin, `limo_nav2` localizes (AMCL), plans and executes a `NavigateToPose`
to the destination using the `RegulatedPurePursuitController` — tested via
`ros2 action send_goal`, with no manual intervention.

```
.
├── Dockerfile
├── docker-compose.yml
├── setup.sh            # prepares .env, X11 and the patched limo_ros2 clone
├── GUIA-BASIC.md       # how to use it (PT)
├── GUIA-BASIC.en.md    # how to use it (EN)
├── README.md           # decisions and fixes (PT)
├── README.en.md        # this file: decisions and fixes (EN)
├── patches/
│   └── limo_ros2-fixes.patch
└── ws/
    └── src/
        ├── limo_ros2/  # cloned by setup.sh, not versioned here
        ├── limo_slam/  # slam_toolbox configuration (versioned here)
        └── limo_nav2/  # Nav2 configuration (versioned here)
```

To set the environment up on a new machine: `./setup.sh`, then
`docker compose build`. Details in [GUIA-BASIC.en.md](GUIA-BASIC.en.md).

---

# Part 1 — Environment decisions

## Why Humble and Gazebo Classic

The `agilexrobotics/limo_ros2` repository has a `humble` branch written for
Gazebo Classic: the plugins are `libgazebo_ros_ackermann_drive.so`,
`libgazebo_ros_ray_sensor.so`, `libgazebo_ros_camera.so`. Porting to
`gz`/Harmonic would mean rewriting every plugin, xacro and launch file. Humble
is the natural match for this codebase, and Gazebo Classic comes with it.

The Gazebo Classic end-of-life notice (January 2025) shows up in the window bar
and is expected. It does not affect the simulation.

## Isolation from the other container on this machine

The machine already runs a `ros2-docker` container (ROS 2 Jazzy + MRS UAV
System) with `network_mode: host` and `ROS_DOMAIN_ID=0`.

This environment uses `ROS_DOMAIN_ID=42`.

Since both containers share the host network, `ROS_DOMAIN_ID` is the **only**
thing keeping one's topics from showing up in the other. Changing that value
without checking what else is running brings the crosstalk back. To verify, with
the simulation running: `ros2 topic list` must show nothing from the MRS UAV
stack.

`network_mode: host` was kept because it simplifies DDS (no NAT, no discovery
configuration) — the price is precisely depending on the domain for isolation.

## The container runs as a non-root user (UID/GID 1000)

This was the most consequential decision, and it was made **after**
investigating how X works on this machine.

**What was found:** the session is COSMIC on Wayland, with Xwayland on
`DISPLAY=:1`. Running `xhost` reports:

```
access control enabled, only authorized clients can connect
SI:localuser:<your-user>
```

In other words, **there is no authentication cookie** (`~/.Xauthority` did not
even exist). Xwayland authorizes by Unix socket credentials (`SO_PEERCRED`):
whoever holds the user's UID gets in, anyone else does not.

**Consequence:** a container running as root is rejected, and the usual fix is
`xhost +local:docker` on every login. Running the container with **UID 1000**
makes it match that rule automatically, and `xhost` becomes unnecessary — for
good, with no autostart entry or session script.

**An equally important side benefit:** with a root container, everything
`colcon build` produces in the bind mount (`build/`, `install/`, `log/`) is
owned by root on the host, and cleaning or editing requires `sudo`. With UID
1000, files are born owned by the user.

The container has passwordless `sudo`, which `rosdep install` needs in order to
install apt packages.

Worth noting: in `xhost +local:docker`, the usual incantation, the word `docker`
is purely decorative — `xhost` only reads the `local:` prefix and opens access
to any local user. The precise equivalent would be `xhost +SI:localuser:root`.
Neither is needed here.

## `group_add: ["44", "992"]`

These are the **host's** `video` and `render` GIDs (`getent group video
render`). Since the container no longer runs as root, it must belong to those
groups to open `/dev/dri/card*` and `/dev/dri/renderD*` — without them, no Mesa
acceleration.

These numbers are specific to this machine. On another host, check first.

## `.Xauthority` mounted, but empty

The volume was kept as originally specified, and the file exists on the host,
empty (0 bytes). Two reasons:

1. A bind mount whose source does not exist makes Docker **create a directory**
   in its place — `~/.Xauthority` would become a folder.
2. Generating a real cookie with `xauth generate :1 . trusted` was attempted and
   failed: COSMIC's Xwayland does not expose the `SECURITY` extension. There is
   no flag around it.

Fabricating a cookie with `mcookie` would work, but for a crooked reason — the
server would not know it, and the connection would pass purely on the socket
credential rule. It would be a file that looks like authentication without
authenticating anything. The empty file is more honest and has the same effect.

## Dockerfile decisions

| Decision | Why |
|---|---|
| `ARG DEBIAN_FRONTEND` instead of `ENV` | with `ENV` the variable would be baked into the image, and every `apt install` run later inside the container would silently inherit non-interactive mode |
| `rm -rf /var/lib/apt/lists/*` in the same layer as `apt-get install` | this is what keeps the apt cache out of the image; in a separate layer the cache would already be committed |
| Side effect of the above | `rosdep install` inside the container needs `sudo apt-get update` first, otherwise there is no package index |
| `sudo` installed in its own layer | the main `apt-get install` is the expensive layer; leaving it byte-for-byte untouched lets rebuilds reuse the cache |
| no `rosdep init` | the `osrf/ros` image already ships `/etc/ros/rosdep/sources.list.d/20-default.list`; calling it again fails with "already exists" |
| `rosdep update` runs as user `limo` | so the cache lands in the HOME of whoever will run `rosdep install` |
| `--no-install-recommends` | smaller image; `ros-*` packages declare what they need in `Depends`. If something graphical turns out missing, drop the flag |
| conditional source in `.bashrc` | `[ -f ~/ws/install/setup.bash ]` avoids breaking the shell before the first `colcon build` |

## `colcon build --symlink-install`

`install/` points at the files in `src/` instead of copying them. Since `ws/` is
a bind mount, editing launch files, `.xacro`, `.rviz` or worlds **on the host**
takes effect inside the container without rebuilding. During the debugging
described below, this shortened each test cycle from minutes to seconds.

---

# Part 2 — Fixes to limo_ros2

Upstream (`agilexrobotics/limo_ros2`, branch `humble`) **does not build, and
does not run** without the changes below. All but the last are in the `limo_car`
package. To see the diffs: `cd ws/src/limo_ros2 && git show humble-fixes`.

The first three block the build. The next four only show up at runtime: the
package compiles cleanly and the simulation comes up broken.

## 1. `CMakeLists.txt` — installing directories that do not exist

```
install(DIRECTORY launch  gazebo log meshes rviz src urdf worlds ...)
```

`log`, `src` and `worlds` do not exist in the package, and CMake aborts when
asked to install a declared but missing directory. `log` and `src` were removed.
`worlds` was kept because the directory now exists (item 4).

## 2. `package.xml` — `<depend>rviz</depend>`

`rviz` is the ROS 1 package name. On ROS 2 it is `rviz2`, and rosdep cannot
resolve the `rviz` key. Fixed to `rviz2`.

A detail that confirms the diagnosis: `limo_description`, in the same
repository, already has that line **commented out** with `rviz2` active. The
author fixed it there and forgot it here.

## 3. `package.xml` — `<depend>libgazebo_ros</depend>`

It exists neither as a ROS package nor as a rosdep key. Verified by parsing the
official Humble `distribution.yaml` (2345 packages):

| key | exists in Humble |
|---|---|
| `rviz` | no |
| `rviz2` | yes |
| `libgazebo_ros` | **no** |
| `gazebo_ros` | yes |

Fixed to `gazebo_ros`. Without it, `rosdep install` stops with
`Cannot locate rosdep definition for [libgazebo_ros]`.

## 4. `worlds/empty_world.model` — missing world

The launch file builds `world_path` from `worlds/empty_world.model`, a file that
is not in the repository.

**There were two ways out:** create the world inside the package, or point the
launch file at a world already shipped by `gazebo_ros`. **The first was chosen**,
for two reasons:

1. The world stays versioned in the workspace and **editable**. It is a bind
   mount from the host, so adding obstacles to exercise SLAM and Nav2 is just
   editing a file. A `gazebo_ros` world would live in `/opt/ros/humble/share/`,
   inside the image, and any edit would die on the next `docker compose build`.
2. Minimal divergence from upstream: it restores a file the author clearly had
   and did not commit, rather than rewriting the launch file.

The world currently has a ground plane, a sun, a closed 10x10 m room, two boxes
and a cylinder. The inner obstacles are **deliberately asymmetric**: smooth,
symmetric walls give the scan matcher few features, and the `slam_toolbox` map
drifts.

## 5. `launch/ackermann_gazebo.launch.py` — the world was never loaded

Found while reading the launch file: `world_path` was passed as a launch
argument to `ackermann.launch.py`, which **only declares `use_sim_time`** and
ignores `world` entirely. The include that actually starts Gazebo received no
arguments at all — Gazebo always opened with the default `empty.world` from
`gazebo_ros`.

`world_path` was therefore dead code. And since `os.path.join` merely
concatenates strings without touching the disk, the missing folder **never
caused a launch error** — what broke was the `install()` from item 1.

Fixed by moving `launch_arguments={'world': world_path}` to the
`gazebo_ros/gazebo.launch.py` include. Without this, the world created in item 4
could be edited with no visible effect — a nastier trap than the original bug.

## 6. `gazebo/ackermann_with_sensor.xacro` — the robot macro was never called

**Symptom:** `spawn_entity` stuck on `Waiting for entity xml on
robot_description`, RViz with no data at all, empty Gazebo.

**Root cause:** the file includes `ackermann.xacro`, which **defines** the
`limo_ackermann` macro — but never instantiates it. The generated URDF came out
with the three sensors and their joints pointing at a `base_link` that was never
created. `robot_state_publisher` aborted (exit code -6):

```
Failed to build tree: parent link [base_link] of joint [depth_camera_joint] not found.
```

With it dead, nobody published `/robot_description` (confirmed:
`Publisher count: 0`), and `spawn_entity` waited forever.

**Fix:** added `<xacro:limo_ackermann />`. The URDF went from 210 lines of pure
sensor payload to the robot's 12 links, `base_link` among them.

A detail that muddies the diagnosis: `xacro` processes the file **without
error** and emits valid XML. The problem is semantic, not syntactic — only the
URDF parser complains.

## 7. `gazebo/ackermann.xacro` — `base_footprint` commented out

**Symptom:** with the robot finally spawning, RViz showed `Global Status: Ok`
and still drew nothing.

**Root cause:** the `base_footprint` link and the `base_joint` were inside an XML
comment. But two consumers depend on that frame: the plugin
(`<robot_base_frame>base_footprint</robot_base_frame>`) and `gazebo.rviz` (Fixed
Frame). The result was two disconnected TF trees:

| publisher | tree |
|---|---|
| `ackermann_controller` (Gazebo plugin) | `odom → base_footprint → wheels` |
| `robot_state_publisher` (URDF) | `base_link → laser_link, depth_camera_link, imu_link` |

The verdict from `tf2_echo`: *"Could not find a connection between
'base_footprint' and 'base_link' because they are not part of the same tree. Tf
has two or more unconnected trees."*

RViz had `/scan` in `base_link` and the Fixed Frame in `base_footprint`, with no
path between them.

**Fix:** block uncommented, restoring `base_footprint → base_link` (0.15 m
offset).

**Why this does not create a duplicate publisher for the wheels:** there is no
`joint_state_publisher` in the launch, so `robot_state_publisher` does not
publish the `continuous` joints (the wheels) — only the fixed ones. The wheels
come from the plugin. The two sources complement each other rather than compete.

## Usability adjustments

Three smaller items, applied after the simulation was validated:

| File | Change | Why |
|---|---|---|
| `gazebo/sensor.xacro` | `<frame_name>${frame_prefix}_link</frame_name>` on the lidar plugin | without it Gazebo lumps `laser_link` (fixed joint) into `base_link`, and `/scan` came out with `frame_id: base_link` — the laser measured from the chassis center, ~12 cm behind its physical position |
| `rviz/gazebo.rviz` | `RobotModel` display reading `/robot_description` | the upstream config has Grid, LaserScan and Image, none of which draws the robot |
| `worlds/empty_world.model` | room and obstacles | in an empty world every lidar ray returns infinity and RViz has nothing to show |

## 8. `.gitignore` — the rule that probably caused bug 4

While versioning the fixes, the world created in item 4 did not show up in
`git status`. The reason:

```
.gitignore:117:*.mod*    limo_car/worlds/empty_world.model
```

Upstream's `.gitignore` has `*.mod*`, which matches `empty_world.model`.

This is almost certainly the **origin of bug 4**: the author had the world on
their machine, `.gitignore` silently excluded it from the commit, and the
repository was published with a launch file pointing at a file that only existed
locally.

Fixed with an explicit exception:

```
!limo_car/worlds/*.model
```

Without it, the same disappearance would repeat in the patch generated from this
clone.

---

# Part 3 — SLAM (the `limo_slam` package)

`slam_toolbox` configuration for mapping the simulated world. Usage lives in
[GUIA-BASIC.en.md](GUIA-BASIC.en.md); the decisions live here.

## Why a separate package instead of putting it in `limo_car`

`limo_car` is AgileX's code. Anything added there would land in
`patches/limo_ros2-fixes.patch`, mixing bug fixes with new functionality and
making both patch review and future upstream updates harder.

Since this repository's `.gitignore` only excludes `ws/src/limo_ros2/`, a
package under `ws/src/limo_slam/` is versioned here directly, with no patch
involved.

```
ws/src/limo_slam/
├── config/mapper_params_online_async.yaml
├── launch/slam.launch.py
└── rviz/slam.rviz
```

## Why `online_async` and not `sync`

Synchronous mode blocks waiting for each scan to be processed before accepting
the next one. With Gazebo, RViz and SLAM competing for the same CPU, the queue
grows and the map comes out blurry. The asynchronous mode drops scans when it
cannot keep up, which for teleoperated mapping is the desirable behaviour — and
it is the mode `slam_toolbox` itself recommends for this case.

## Parameters that differ from the defaults, and why

| Parameter | Default | Here | Reason |
|---|---|---|---|
| `base_frame` | `base_footprint` | `base_footprint` | it matches, but this is the frame that only exists because fix 7 restored it |
| `max_laser_range` | `20.0` | `8.0` | the URDF's lidar reaches 8 m; at 20 the SLAM would treat as valid readings the sensor never produces |
| `resolution` | `0.05` | `0.05` | 5 cm per cell, suitable for a 10x10 m room |
| `minimum_travel_distance` | `0.5` | `0.1` | the LIMO is small and slow; at 0.5 m a lap around the room would discard almost every scan |
| `minimum_travel_heading` | `0.5` | `0.1` | same reason, for rotation |
| `scan_buffer_maximum_scan_distance` | `10.0` | `8.0` | consistency with the sensor's actual range |
| `use_sim_time` | `false` | `true` | time comes from Gazebo's `/clock` |

## The launch file does not start Gazebo

`slam.launch.py` starts only `slam_toolbox` and an RViz. The simulation runs in
another terminal.

That is deliberate: tuning SLAM parameters is a trial-and-error loop, and
restarting SLAM without tearing down the world, the robot and its current pose
saves a lot of time. The price is one extra terminal and a second RViz window —
which can be turned off with `rviz:=false`.

## What the simulation imposes on mapping

**240° field of view.** `sensor.xacro` sets `min_angle`/`max_angle` to ±2.094
rad. This is not a 360° lidar: the robot is blind behind, and mapping well
requires covering the room in both directions. That comes from the real LIMO's
model, it is not a configuration mistake.

**Odometry that is too good.** The Gazebo plugin publishes `odom` from the
simulation's ground truth pose, without the slippage a real robot has. The map
tends to come out better than it would on physical hardware — worth keeping in
mind before trusting these parameters on the real thing.

# Part 4 — Nav2 (the `limo_nav2` package)

Nav2 configuration to navigate autonomously with the simulated LIMO, using a
map saved by `slam_toolbox`. Usage is in [GUIA-BASIC.en.md](GUIA-BASIC.en.md);
the decisions live here.

```
ws/src/limo_nav2/
├── config/nav2_params.yaml
├── launch/nav2.launch.py
└── rviz/nav2.rviz
```

## Why reuse `nav2_bringup`'s `bringup_launch.py`

`nav2_bringup` already handles container composition
(`component_container_isolated`), the activation order of the
`lifecycle_manager`s (localization first, then navigation) and the default
behavior tree. Rebuilding that by hand would diverge from an upstream-maintained
package for no gain — `limo_nav2/launch/nav2.launch.py` only declares the
arguments specific to this robot (map path, `params_file`) and includes
`bringup_launch.py` with them, the same way `ackermann_gazebo.launch.py`
includes `gazebo_ros`'s `gazebo.launch.py`.

## `nav2_params.yaml` starts from `nav2_bringup`'s default template

Copied straight out of the image itself
(`/opt/ros/humble/share/nav2_bringup/params/nav2_params.yaml`) and adjusted,
with every deviation marked `# [adjusted]` in the file. The main ones:

| Parameter | Default | Here | Why |
|---|---|---|---|
| `*.robot_base_frame` / `amcl.base_frame_id` | `base_link` | `base_footprint` | same frame the Gazebo Ackermann plugin and `limo_slam` already use — see fix 7 in Part 2 |
| `amcl.laser_max_range` | `100.0` | `8.0` | actual range of the simulated lidar (`sensor.xacro`) |
| `amcl.set_initial_pose` / `initial_pose` | off | `(0, 0, 0)` | the robot always spawns at that pose (fixed `spawn_x/y/z/yaw` in `ackermann_gazebo.launch.py`), and it is the same origin used by the saved map — skips the manual "2D Pose Estimate" in RViz |
| `local_costmap.plugins` | `voxel_layer` (3D, assumes a depth camera feeding the costmap) | `obstacle_layer` (2D) | this robot only has a 2D lidar feeding the costmap; keeping `voxel_layer` would be unused complexity |
| `*.robot_radius` | `0.22` (TurtleBot radius) | `0.18` | half the LIMO chassis diagonal (`base_x_size`/`base_y_size` = 0.19x0.31, from `ackermann.xacro`) |
| `controller_server.FollowPath.plugin` | `dwb_core::DWBLocalPlanner` | `nav2_regulated_pure_pursuit_controller::RegulatedPurePursuitController` | see next section |
| `velocity_smoother.max_velocity` | `[0.26, 0.0, 1.0]` (TurtleBot) | `[0.3, 0.0, 1.0]` | same ceiling suggested in `GUIA-BASIC.en.md` for teleop |

## Why `RegulatedPurePursuitController` instead of the default `DWB`

`DWB` evaluates trajectories by sampling independent linear and angular
velocities, which includes rotating in place — natural for differential
drive, but something the LIMO simply cannot do: as `GUIA-BASIC.en.md`
documents ("Ackermann quirk"), with zero linear velocity the angular command
does nothing. Running `DWB` for navigation would have the behavior tree
attempting alignments the robot ignores, until it hits `Controller patience
exceeded`.

`RegulatedPurePursuitController` follows a lookahead point on the planned
path, with `use_rotate_to_heading: false` and a `min_turning_radius` derived
from the robot's real kinematics:

```
min_turning_radius = wheelbase / tan(max_steer)
                    = 0.24 / tan(0.5236 rad)
                    ≈ 0.42 m
```

`wheelbase` and `max_steer` come from `ackermann.xacro` (the `wheelbase`
property and the `max_steer` parameter of the
`libgazebo_ros_ackermann_drive.so` plugin). The controller never requests a
turn tighter than the robot can physically make.

`allow_reversing: false` was kept — reversing with simultaneous steering was
not validated against this controller, and no current use of the robot needs
it.

## `amcl.robot_model_type` stays `DifferentialMotionModel`

Nav2 has no dedicated Ackermann motion model. `DifferentialMotionModel` is
the usual approximation (it assumes the robot does not slip sideways, which
holds for both diff-drive and Ackermann) — an approximation, not an exact
model of the LIMO's kinematics, but it is what upstream Nav2 offers.

## Validation

Tested end to end in this environment: a map generated and saved with
`slam_toolbox`, the simulation relaunched from scratch (robot back at the
origin, consistent with AMCL's fixed initial pose), `limo_nav2` brought up,
and a goal sent via `ros2 action send_goal /navigate_to_pose ...` — the robot
planned, followed the path, and the action finished with `SUCCEEDED`.

Found during testing, not a defect in the package: bringing up Nav2
**without** restarting the simulation after driving the robot during mapping
makes AMCL's fixed initial pose (always `(0,0,0)`) diverge from the robot's
real pose (wherever driving left it). The symptom is
`RegulatedPurePursuitController detected collision ahead!` in a loop, because
the local costmap gets evaluated from a wrong `map → odom` transform. The fix
is to always relaunch `ackermann_gazebo.launch.py` from scratch before Nav2 —
documented in section 7 of `GUIA-BASIC.en.md`.

# Part 5 — Portability

This environment was built on a specific machine (Pop!_OS, COSMIC on Wayland,
integrated Intel GPU). Three things depend on the machine, and all of them go
through the `.env` generated by `setup.sh`:

| Variable | What it is | Why it varies |
|---|---|---|
| `USER_UID` / `USER_GID` | file ownership and identity towards Xwayland | the first user is usually 1000, but not always |
| `VIDEO_GID` / `RENDER_GID` | access to `/dev/dri/*` | differs across distributions (44 and 992 here; on Ubuntu 24.04 render is usually 993) |
| `XAUTH_FILE` | X authority file | on GNOME/Wayland it is `/run/user/<uid>/.mutter-Xwaylandauth.*`, not `~/.Xauthority` |

`docker-compose.yml` reads these variables with this machine's values as
defaults (`${RENDER_GID:-992}`), so it still works here without a `.env` — but on
any other machine `setup.sh` is mandatory.

## What can still go wrong elsewhere

- **No `/dev/dri`** (VM, WSL, headless server): `docker compose up` **fails**,
  it does not degrade. `setup.sh` warns about it. The way out is removing the
  `devices:` section and accepting software rendering.
- **NVIDIA GPU**: `/dev/dri` exists, but real acceleration needs
  `nvidia-container-toolkit` and runtime configuration, which this environment
  does not set up.
- **X authorization**: the conclusion that `xhost` is unnecessary holds for
  compositors using the `SI:localuser:` rule — which is the case for COSMIC
  here. Others authorize differently. If Gazebo complains about the display,
  `xhost +SI:localuser:root` fixes it immediately, and then it is worth finding
  out how that compositor authorizes.
- **Docker Desktop (macOS/Windows)**: `network_mode: host` and the Linux X11
  socket do not apply. This environment assumes Docker Engine on Linux.

## `.dockerignore`

The `Dockerfile` has no `COPY` or `ADD` — the image is assembled purely through
`apt`. Without a `.dockerignore`, `docker compose build` shipped the whole
directory (259 MB with the workspace built) to the daemon on every build,
using none of it.

---

# Part 6 — Version control

Two layers of git, on purpose:

**1. `~/limo-docker`** — the infrastructure repository: `Dockerfile`,
`docker-compose.yml`, the documentation and the patch. Its `.gitignore` excludes
build artifacts (`ws/build/`, `ws/install/`, `ws/log/`) and the `limo_ros2`
clone itself, which has its own git.

**2. `ws/src/limo_ros2`** — the upstream clone. The fixes are committed on the
local branch **`humble-fixes`**, on top of AgileX's `dcc5a86`. That protects
them from an accidental `git checkout`.

**The bridge between the two:** `patches/limo_ros2-fixes.patch`, versioned in the
outer repository. It makes this repo self-sufficient — no fork of `limo_ros2`
required. Reproducing the environment from scratch means running `./setup.sh`,
which does:

```bash
cd ws/src
git clone -b humble https://github.com/agilexrobotics/limo_ros2.git
cd limo_ros2
git am < ../../../patches/limo_ros2-fixes.patch
```

If upstream moves and `git am` refuses, `setup.sh` automatically retries with
`git am --3way` before giving up.

When changing `limo_ros2` from now on, commit to `humble-fixes` and regenerate
the patch:

```bash
cd ws/src/limo_ros2
git format-patch dcc5a86 --stdout > ../../../patches/limo_ros2-fixes.patch
```

---

# Part 7 — Debugging method

Worth recording, because the same path will serve the next problem.

Items 6 and 7 share a treacherous property: **the package compiles cleanly**.
`colcon build` succeeds, the simulation opens, windows appear — and nothing
works. Two things unlocked the diagnosis:

1. **Capturing the launch log to a file** instead of scrolling the terminal:
   `ros2 launch ... > /tmp/launch.log 2>&1`. The fatal `robot_state_publisher`
   error happens in the first 200 ms and gets buried under hundreds of lines of
   ALSA noise (the container has no sound card).

2. **Inspecting the live system from another terminal**, via
   `docker compose exec limo bash`:

   | Command | What it revealed |
   |---|---|
   | `ros2 node list` | `robot_state_publisher` was not among the nodes |
   | `ros2 topic info /robot_description --verbose` | `Publisher count: 0` — ruled out a QoS mismatch |
   | `ros2 run tf2_ros tf2_echo A B` | "two or more unconnected trees", in plain text |
   | `ros2 topic echo /tf --once` | showed the plugin publishing wheels off `base_footprint` |

One hypothesis was tested and **discarded** along the way: the xacro was
suspected, but `xacro file.xacro > /tmp/limo.urdf` ran without error. That
redirected the investigation from the URDF's producer to its consumer, which is
where the problem actually was.

---

# Known limitations

- **No `joint_state_publisher`:** `robot_state_publisher` does not animate the
  wheels in visualization. This affects neither physics nor navigation — Gazebo
  is the source of truth for motion.
- **`urdf/limo_ackerman_base.xacro` is orphaned:** it defines a correct
  `base_footprint`, but nothing includes it (it only appears in a commented line
  of `display_ackermann.launch.py`). Left untouched.
- **`limo_base/scripts/` is not installed:** the package's `CMakeLists.txt`
  installs `launch` and `src`, but not `scripts`. It does not break the build and
  is not part of the Gazebo simulation.
- **`amcl.robot_model_type` is an approximation:** Nav2 has no dedicated
  Ackermann motion model; `DifferentialMotionModel` is used instead (see
  Part 4).
- **`allow_reversing: false` on the controller:** reversing with simultaneous
  steering was not validated against `RegulatedPurePursuitController`. No
  current use of the robot needs it.
- **No sample map is versioned:** `ws/maps/` is not part of the repository
  (maps are specific to each world/run). Generate your own using section 6 of
  `GUIA-BASIC.en.md` before using Nav2.

# Suggested next steps

1. ~~`slam_toolbox` to map the room~~ — done, the `limo_slam` package (Part 3).
2. ~~Save the map and bring up Nav2 with AMCL~~ — done, the `limo_nav2`
   package (Part 4).
3. ~~Tune Nav2 for ackermann kinematics~~ — done:
   `RegulatedPurePursuitController` with `min_turning_radius` derived from the
   real `wheelbase`/`max_steer` (Part 4).
4. Validate Nav2 against a carefully mapped room (a full pass around the
   room in both directions, driven slowly) — the map used for the Part 4
   validation was generated by a quick scripted spin, good enough to test the
   package but not for real use (see "Found during testing" in Part 4).
5. Consider Ackermann-compatible recovery behaviors — the default `Spin`
   behavior in Nav2's behavior tree requests pure rotation, which the LIMO
   cannot do; today it just burns its `time_allowance` without moving the
   robot.
