# src 目录源码反向调研

## 调研背景

对 `~/racecar/src/racecar/src/` 目录下所有 C++ 源文件进行反向调研，追踪每个文件在构建系统、启动系统和运行时中的实际生效情况。回答核心问题：**哪个文件是活的？哪个文件改了能生效？怎么编译？**

---

## 1. 目录文件总览

| 文件 | 大小 | CMakeLists.txt | 被编译 | 被启动 | 运行时生效 |
|------|------|:---:|:---:|:---:|:---:|
| `car_controller_new.cpp` | 30KB | × | × | × | **死代码** |
| `car_controller_new copy.cpp` | 20KB | × | × | × | 死代码（去注释版） |
| `car_controller_new copy 2.cpp` | 24KB | × | × | × | 死代码（WIP 版） |
| `my_car_control_new.cpp` | 6.8KB | ✓ | ✓ | × | 可运行但不自动启动 |
| `car_control_all.cpp` | 5.5KB | ✓ | ✓ | × | 可运行但不自动启动 |
| `laser_2d_new.cpp` | 4.6KB | ✓ | ✓ | × | 可运行但不自动启动 |
| `scan_node.cpp` | 8KB | ✓ | ✓ | × | 可运行但不自动启动 |

**关键结论：这个目录下的 7 个文件中，4 个被编译但没有任何启动脚本会运行它们，3 个从未被编译。**

---

## 2. 构建系统分析 (CMakeLists.txt)

### 2.1 注册的可执行目标

`~/racecar/src/racecar/CMakeLists.txt` 中仅有 4 个 `add_executable`：

```cmake
add_executable(laser_2d_new src/laser_2d_new.cpp)          # 第52行
add_executable(my_car_control_new src/my_car_control_new.cpp)  # 第53行
add_executable(scan_node src/scan_node.cpp)                 # 第54行
add_executable(car_control_all src/car_control_all.cpp)     # 第55行
```

**`car_controller_new.cpp` 及其两个副本从未出现在 CMakeLists.txt 中。**

### 2.2 安装目标

```cmake
install(TARGETS
  laser_2d_new
  my_car_control_new
  scan_node
  car_control_all
  DESTINATION lib/racecar/
)
```

安装后位于：`~/racecar/install/racecar/lib/racecar/`，可用 `ros2 run racecar <executable>` 启动。

### 2.3 编译方法

```bash
# 仅编译 racecar 包（最快）
cd ~/racecar && colcon build --packages-select racecar

# 或编译全部
cd ~/racecar && colcon build
```

编译后需 source 环境：
```bash
source ~/racecar/install/setup.bash
```

---

## 3. 启动系统分析

### 3.1 启动脚本一览

| 脚本 | 用途 | 是否启动这些 C++ 节点？ |
|------|------|:---:|
| `car.sh` | 传感器+底盘 | 否 |
| `nav.sh` | 传感器+底盘+导航 | 否 |
| `nav_one.sh` | 旧版导航（cmd_vel） | 否 |
| `gmapping.sh` | SLAM 建图 | 否 |

### 3.2 脚本实际启动的节点

以 `nav.sh` 为例，调用链：

```
nav.sh
├── Run_car.launch.py → 启动:
│   ├── lslidar_driver（激光雷达）
│   ├── hipnuc_imu（IMU）
│   ├── encoder_node（编码器）
│   ├── robot_localization (EKF)
│   ├── joint_state_publisher
│   ├── static_transform_publisher ×3
│   └── racecar_driver_node（底盘驱动）  ← 最终执行器
│
├── Run_nav.launch.py → 启动:
│   ├── bringup_launch.py
│   │   ├── AMCL localization（定位）
│   │   ├── planner_server（全局规划）
│   │   └── bt_navigator（行为树导航）
│   │
│   └── 注意：controller_server 被注释掉了！
│
└── ros2 run nav2_waypoint_cycle（航点循环）
```

**没有任何地方启动 `my_car_control_new`、`car_control_all`、`laser_2d_new` 或 `scan_node`。**

### 3.3 被注释掉的 Nav2 控制器

`bringup_launch.py` 中：

```python
lifecycle_nodes = [
    # 'controller_server',     ← 注释掉，Nav2 局部路径跟踪被禁用
    # 'smoother_server',        ← 注释掉
    'planner_server',
    # 'behavior_server',        ← 注释掉
    'bt_navigator',
    # 'waypoint_follower'
]
```

这意味着 Nav2 的局部路径跟踪（RegulatedPurePursuit / DWB）未运行。Nav2 只提供全局路径规划。

---

## 4. 实际导航控制链路

### 当前状态

```
用户操作（遥控 / 航点 / 循迹脚本）
        │
        ▼  Python 脚本直接控制
  /car_cmd_vel  ←── racecar_teleop.py / go.py / zhuitong.py / line_follow.py
        │
        ▼  racecar_driver_node 将 Twist 转为 PWM
  /dev/car（PWM 下位机）
```

### 预期完整状态（如果启用 car_controller_new）

```
Nav2 planner_server  →  /plan  (全局路径)
Nav2 bt_navigator    →  /goal_pose  (导航目标)
                              │
                              ▼
              car_controller_new (L1 路径跟踪)
                              │
                              ▼
                       /car_cmd_vel
                              │
                              ▼
                    racecar_driver_node → PWM
```

---

## 5. 文件详细说明

### 5.1 `car_controller_new.cpp`（30KB，死代码）

**节点名**: `art_car_controller`

**功能**: L1 控制律（Pure Pursuit 变体）路径跟踪控制器，是 Nav2 路径规划的底层执行器。

**订阅的话题**:
- `/odom_combined` (Odometry) — EKF 融合里程计
- `/plan` (Path) — Nav2 规划的全局路径
- `/goal_pose` (PoseStamped) — 导航目标点
- `/arrfinal` (Float64) — 停止标志（0/1/2/3）
- `/line_wight` (Float64) — 车道线宽度
- `/light` (String) — 红绿灯状态 ("red"/"green")

**发布的话题**:
- `/car_cmd_vel` (Twist) — 速度命令
- `car_path` (Marker) — 路径可视化

**现状**: 代码完整但从未在 CMakeLists.txt 注册，从未被编译。

### 5.2 `car_controller_new copy.cpp` / `car_controller_new copy 2.cpp`

与原版核心代码完全相同，仅注释风格差异：
- **copy**: 去掉中文注释
- **copy 2**: 加英文注释，注释掉 `initMarker()` 和 `encoder_sub`（WIP 中）

也是死代码。

### 5.3 `my_car_control_new.cpp`（6.8KB，已编译但不启动）

**节点名**: （类名 `MyCarControl`）

**功能**: 简单的 PID 控制器，订阅 `/carpose` (Pose2D) 和里程计，输出到 `/car_cmd_vel`。

**现状**: 已编译已安装，但没有任何启动脚本会运行它。若需使用：

```bash
ros2 run racecar my_car_control_new
```

### 5.4 `car_control_all.cpp`（5.5KB，已编译但不启动）

**节点名**: `lidar_processor`

**功能**: 基于激光雷达的简单避障。订阅 `/scan`，输出到 `/car_cmd_vel`。启动后前 8 秒默认前进+左转，之后根据雷达数据避障。

**现状**: 已编译已安装，不自动启动。

```bash
ros2 run racecar car_control_all
```

### 5.5 `laser_2d_new.cpp`（4.6KB，已编译但不启动）

**功能**: 二维激光雷达数据处理节点。

**现状**: 已编译已安装，不自动启动。

### 5.6 `scan_node.cpp`（8KB，已编译但不启动）

**功能**: 激光扫描数据处理节点。

**现状**: 已编译已安装，不自动启动。

---

## 6. 如何让 `car_controller_new.cpp` 生效

### 步骤 1：加入 CMakeLists.txt

在 `~/racecar/src/racecar/CMakeLists.txt` 第 55 行（`add_executable(car_control_all ...)`）后插入：

```cmake
add_executable(car_controller_new src/car_controller_new.cpp)
ament_target_dependencies(car_controller_new
  rclcpp
  geometry_msgs
  nav_msgs
  tf2_ros
  tf2_geometry_msgs
  visualization_msgs
  std_msgs
  sensor_msgs
  message_filters
)
```

在 `install(TARGETS ...)` 中追加：

```cmake
install(TARGETS
  laser_2d_new
  my_car_control_new
  scan_node
  car_control_all
  car_controller_new    # ← 新增
  DESTINATION lib/racecar/
)
```

### 步骤 2：编译

```bash
cd ~/racecar && colcon build --packages-select racecar
```

### 步骤 3：验证编译

```bash
source ~/racecar/install/setup.bash
ros2 run racecar car_controller_new
```

### 步骤 4：集成到启动（二选一）

**方案 A** — 添加到 `Run_car.launch.py`（传感器启动时一并启动）：

```python
Node(
    package='racecar',
    executable='car_controller_new',
    name='art_car_controller',
    output='screen',
),
```

**方案 B** — 单独启动（适合调试）：

```bash
ros2 run racecar car_controller_new
```

---

## 7. 常见问题

### Q1: 我改了一个 `.cpp` 文件，怎么确认生效了？

```bash
# 1. 重新编译
cd ~/racecar && colcon build --packages-select racecar

# 2. 确认编译成功（无 error）
# 3. 确认可执行文件已更新
ls -la ~/racecar/install/racecar/lib/racecar/car_controller_new  # 时间戳应为刚编译的时间

# 4. source 新环境
source ~/racecar/install/setup.bash

# 5. 启动节点
ros2 run racecar car_controller_new
```

### Q2: `colcon build` 后要重启机器人吗？

不需要重启整个系统。只需：
1. 重新 source 环境
2. `ros2 run` 启动新节点
3. 新节点会自动订阅已有话题

如果替换正在运行的节点，先 `Ctrl+C` 停掉旧节点再启动新节点即可。

### Q3: 为什么 controller_server 被注释掉了？

这是设计选择。Nav2 自带的局部规划器（RegulatedPurePursuit / DWB）被禁用，改为预留自定义 L1 控制器（`car_controller_new.cpp`）的集成位置。但目前该控制器也未被编译和部署，导致路径跟踪层悬空——一切运动控制由 Python 脚本直接接管。

### Q4: 三个 car_controller 版本有什么区别？

| 版本 | 差异 | 建议 |
|------|------|------|
| `car_controller_new.cpp` | 完整中文注释 | 基于此版本修改 |
| `car_controller_new copy.cpp` | 去掉中文注释 | 可用于发布/分享 |
| `car_controller_new copy 2.cpp` | 注释掉部分代码 | WIP 版本，不推荐使用 |

功能上三者完全一致。建议以原始版为基准进行修改。

---

## 8. 总结

```
┌─────────────────────────────────────────────────────────────────┐
│                    src 目录反向调研结论                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  7 个源文件 = 3 个死代码 + 4 个编译但不自动启动的节点            │
│                                                                  │
│  死代码:                                                        │
│    car_controller_new.cpp          (未进 CMakeLists.txt)         │
│    car_controller_new copy.cpp     (同上)                        │
│    car_controller_new copy 2.cpp   (同上)                        │
│                                                                  │
│  已编译但不自动启动:                                             │
│    my_car_control_new   — PID 控制器                             │
│    car_control_all      — 激光雷达避障                           │
│    laser_2d_new         — 雷达处理                               │
│    scan_node            — 扫描处理                               │
│                                                                  │
│  实际控制链路（当前）:                                           │
│    Python 脚本 → /car_cmd_vel → racecar_driver → PWM → /dev/car │
│                                                                  │
│  预期控制链路（启用 car_controller_new 后）:                     │
│    Nav2 → /plan + /goal_pose → L1 控制器 → /car_cmd_vel → ...  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```
