# nav.yaml 配置详解 — Nav2 全套导航参数

## 文件概述

- **路径**: `~/racecar/src/racecar/config/nav.yaml`
- **用途**: Nav2 全套导航栈的完整配置，包含 AMCL 定位、全局/局部规划器、代价地图、行为服务器等所有组件
- **生效方式**: 修改后重启 `nav.sh` 即可，**无需 colcon build**（仅改配置文件不涉及代码时）
- **运行时调参**: 支持 `ros2 param set` 临时修改测试

> 相关文档：[15-导航调参指南.md](15-导航调参指南.md) — 常见问题的根因分析与调整方案

---

## 目录

1. [AMCL 定位](#1-amcl-定位)
2. [BT Navigator 行为树导航器](#2-bt-navigator-行为树导航器)
3. [Controller Server 局部控制器](#3-controller-server-局部控制器)
4. [代价地图](#4-代价地图)
5. [Planner Server 全局路径规划器](#5-planner-server-全局路径规划器)
6. [Behavior Server 行为服务器](#6-behavior-server-行为服务器)
7. [Waypoint Follower 航点跟随器](#7-waypoint-follower-航点跟随器)
8. [Map Saver 地图保存](#8-map-saver-地图保存)
9. [参数速查表](#9-参数速查表)
10. [运行时调参方法](#10-运行时调参方法)

---

## 1. AMCL 定位

AMCL（Adaptive Monte Carlo Localization）负责在已知地图上确定机器人的位置。使用自适应粒子滤波，在定位不确定时增加粒子数，稳定后减少粒子数以节省计算。

```yaml
amcl:
  ros__parameters:
    base_frame_id: "base_footprint"
    global_frame_id: "map"
    odom_frame_id: "odom_combined"
    scan_topic: /scan
    laser_model_type: "likelihood_field"
    max_particles: 2000
    min_particles: 500
    pf_err: 0.05
    pf_z: 0.99
    update_min_a: 0.06    # 旋转更新阈值 (rad)
    update_min_d: 0.025   # 平移更新阈值 (m)
    set_initial_pose: True
    initial_pose.x: 0.0
    initial_pose.y: 0.0
    initial_pose.yaw: 0.0
    robot_model_type: "nav2_amcl::DifferentialMotionModel"
    sigma_hit: 0.2
    z_hit: 0.7
    z_rand: 0.059
    z_short: 0.24
```

### 关键参数详解

| 参数 | 当前值 | 含义 | 调参建议 |
|------|--------|------|---------|
| `odom_frame_id` | `odom_combined` | 必须与 EKF 输出的里程计坐标系一致 | ❗ 绝不能改错，否则 TF 树断裂 |
| `laser_model_type` | `likelihood_field` | 似然场模型（比 beam 模型更鲁棒，计算更快） | 保持默认 |
| `max_particles` | 2000 | 最大粒子数，越多定位越准但计算越慢 | 1000~3000，CPU 紧张可降低 |
| `min_particles` | 500 | 最小粒子数，定位稳定后保持的下限 | 300~1000 |
| `update_min_a` | 0.06 rad (~3.4°) | 机器人旋转超过此角度才更新粒子滤波器 | 减小 → 更新更频繁（更敏感） |
| `update_min_d` | 0.025 m | 机器人平移超过此距离才更新粒子滤波器 | 减小 → 更新更频繁 |
| `set_initial_pose` | True | 启动时自动设初始位姿为 (0,0,0) | 机器人在原点启动时保持 True |
| `sigma_hit` | 0.2 | 激光击中障碍物的标准差 | 增大 → 对激光测量更宽容 |
| `z_hit` / `z_rand` / `z_short` | 0.7 / 0.059 / 0.24 | 激光测量模型的概率权重，总和应为 1.0 | 一般不用改 |

### 适用场景

- **地图已存在 + 机器人已知大致位置**：`nav.sh` 启动模式
- **需要重新定位**：在 RViz 中使用 "2D Pose Estimate" 按钮，或发布 `/initialpose` 话题

---

## 2. BT Navigator 行为树导航器

控制导航行为树的执行流程，决定如何从起点到终点（规划→控制→检查到达→异常处理）。

```yaml
bt_navigator:
  ros__parameters:
    global_frame: map
    robot_base_frame: base_footprint
    odom_topic: odom_combined
    goal_reached_tol: 0.6      # 到达目标容差 (m)
    bt_loop_duration: 10       # 行为树循环间隔 (ms)
    default_server_timeout: 20 # 动作服务器超时 (ms)
```

### 关键参数详解

| 参数 | 当前值 | 含义 | 调参建议 |
|------|--------|------|---------|
| `goal_reached_tol` | **0.6 m** | 机器人距离目标点多远就认为"已到达" | 增大 → 更容易到达但定位粗糙；减小 → 停得更准但可能永远停不到精确位置 |
| `bt_loop_duration` | 10 ms | 行为树主循环周期 | 一般保持默认 |
| `default_server_timeout` | 20 ms | 调用子行为（如规划、控制）的超时 | 网络/计算紧张时可增大 |

### 注意事项

`goal_reached_tol` 为 0.6m 意味着机器人在目标点半径 0.6m 范围内即判定为到达。如果比赛要求精确停到某个点，需要把这个值调小（如 0.2m）。但调小后可能导致机器人反复挣扎无法满足精度而超时失败。

---

## 3. Controller Server 局部控制器

**这是整个导航栈中最关键的调参区域**。它负责实时跟踪全局路径，输出速度指令。

当前使用 **Regulated Pure Pursuit Controller**（受调节的纯追踪算法），相比经典 Pure Pursuit 增加了弯道减速、碰撞检测等功能。

```yaml
controller_server:
  ros__parameters:
    controller_frequency: 20.0
    odom_topic: odom_combined
    controller_plugins: ["FollowPath"]
    FollowPath:
      plugin: "nav2_regulated_pure_pursuit_controller::RegulatedPurePursuitController"
      desired_linear_vel: 0.33          # 目标线速度 (m/s)
      lookahead_dist: 0.3               # 基础前视距离 (m)
      min_lookahead_dist: 0.3
      max_lookahead_dist: 0.6
      use_velocity_scaled_lookahead_dist: true
      use_regulated_linear_velocity_scaling: true  # 弯道自动减速
      regulated_linear_scaling_min_speed: 0.25     # 弯道最低速度
      allow_reversing: false
      use_collision_detection: false
```

### 3.1 速度参数

| 参数 | 当前值 | 含义 | 调参方向 |
|------|--------|------|---------|
| `desired_linear_vel` | **0.33 m/s** | 最大目标线速度 | **减小** → 更稳但更慢；**增大** → 更快但可能不稳 |
| `controller_frequency` | 20.0 Hz | 控制器运行频率 | 一般不用改 |
| `use_regulated_linear_velocity_scaling` | true | 弯道时根据曲率自动减速 | **建议保持 true** |
| `regulated_linear_scaling_min_speed` | **0.25 m/s** | 弯道减速的下限 | 减小 → 过弯更慢更稳 |

### 3.2 前视距离（核心参数 ⭐）

前视距离是纯追踪算法的核心 — 它决定了机器人在路径上"往前看多远"来决策转向。

> **形象理解**：就像开车时看的远近。看太近（0.3m）→ 频繁急打方向 → 左右晃动。看远一些 → 方向更平滑，但过远会切弯（抄近路）。

| 参数 | 当前值 | 问题 | 建议值 |
|------|--------|------|--------|
| `lookahead_dist` | **0.3m** | ❌ 远小于转弯半径(0.6m)，车没"看到"弯道就已经进弯了 | **0.5~0.8m** |
| `min_lookahead_dist` | **0.3m** | 同上 | **0.4~0.6m** |
| `max_lookahead_dist` | **0.6m** | 上限受限 | **0.8~1.2m** |
| `use_velocity_scaled_lookahead_dist` | true | 速度越快前视越远，动态调整 | 保持 true |

**前视距离与转弯半径的关系**：

```
转弯半径 0.6m ─┬─ 前视 0.3m → 车在弯道内走一步看一步，频繁修正 → ❌ 左右晃
                ├─ 前视 0.6m → 刚好看清弯道形状 → 基本稳定
                └─ 前视 1.0m → 提前预判弯道 → ✅ 平滑过弯（可能轻微切弯）
```

### 3.3 碰撞检测

| 参数 | 当前值 | 含义 | 建议 |
|------|--------|------|------|
| `use_collision_detection` | **false** | ⚠️ 关闭状态，机器人不会主动避撞 | **改为 true** |
| `max_allowed_time_to_collision_up_to_carrot` | 未设置 | 碰撞前允许的反应时间 | 建议设为 2.0 秒 |

### 3.4 接近终点行为

| 参数 | 当前值 | 问题 |
|------|--------|------|
| `min_approach_linear_velocity` | ~0.5 | ❌ **比目标速度(0.33)还高** → 接近终点时减速逻辑异常，导致走走停停 |
| **应改为** | **0.15** | 接近终点时逐渐减速到 0.15m/s，平稳停靠 |

### 3.5 高级参数（可选开启）

```yaml
# 原地旋转对准航向（消除大角度转弯时的犹豫）
use_rotate_to_heading: false → true
rotate_to_heading_min_angle: 0.785  # ~45°，超过此角度先原地旋转再前进
rotate_to_heading_angular_vel: 0.4  # 旋转角速度
```

---

## 4. 代价地图

代价地图是 Nav2 对环境的表示，分为局部（实时避障用）和全局（路径规划用）两层。

### 4.1 局部代价地图

用于实时避障和局部路径规划，**跟随机器人滚动**（rolling window）。

```yaml
local_costmap:
  global_frame: odom_combined
  robot_base_frame: base_footprint
  rolling_window: true      # 跟随机器人移动
  width: 4                  # 4米宽
  height: 4                 # 4米高
  resolution: 0.05          # 0.05米/像素（高精度）
  robot_radius: 0.60        # 机器人半径
  plugins: ["voxel_layer", "inflation_layer"]
```

#### 体素层（voxel_layer）

| 参数 | 当前值 | 含义 |
|------|--------|------|
| 输入话题 | `/scan` | 激光雷达数据 |
| 最大障碍物高度 | 2.0 m | 超过此高度的物体视为可通过 |
| Z 轴体素数 | 16 | 垂直方向分辨率 |
| obstacle_max_range | **2.5 m** | 障碍物检测最大范围 |

> ⚠️ `obstacle_max_range: 2.5` 偏小，建议改为 **4.0**，让局部代价地图充分利用激光雷达数据。

#### 膨胀层（inflation_layer）

| 参数 | 当前值 | 含义 | 建议 |
|------|--------|------|------|
| `inflation_radius` | **0.25 m** | 障碍物膨胀半径 | ⚠️ 0.6m 半径的车仅 0.25m 安全余量 → 建议 **0.5m** |
| `cost_scaling_factor` | 10.0 | 代价衰减速度 | 保持默认 |

### 4.2 全局代价地图

用于全局路径规划，基于静态地图 + 实时障碍物 + 膨胀。

```yaml
global_costmap:
  global_frame: map
  robot_base_frame: base_footprint
  resolution: 0.2           # 0.2米/像素（较粗，计算更快）
  track_unknown_space: true # 未知区域视为自由空间
  plugins: ["static_layer", "obstacle_layer", "inflation_layer"]
```

| 参数 | 当前值 | 含义 | 建议 |
|------|--------|------|------|
| `resolution` | 0.2 m/像素 | 全局地图精度（比局部粗 4 倍） | 保持默认 |
| `inflation_radius` | **0.15 m** | 全局膨胀半径 | ⚠️ 严重偏小，路径几乎贴着墙 → 建议 **0.4m** |
| `track_unknown_space` | true | 未知区域可通行 | 保持 true |

### 4.3 两种代价地图对比

| 维度 | 局部代价地图 | 全局代价地图 |
|------|-------------|-------------|
| 坐标系 | `odom_combined` | `map` |
| 大小 | 4m × 4m 滑动窗口 | 全地图 |
| 分辨率 | 0.05 m/px | 0.2 m/px |
| 图层 | 体素 + 膨胀 | 静态 + 障碍物 + 膨胀 |
| 膨胀半径 | 0.25m ⚠️ | 0.15m ⚠️ |
| 用途 | 实时避障 | 全局路径规划 |

---

## 5. Planner Server 全局路径规划器

使用 **SmacPlanner Hybrid**（Hybrid A* 算法），在离散栅格地图上搜索平滑路径。

```yaml
planner_server:
  ros__parameters:
    planner_plugins: ["GridBased"]
    GridBased:
      plugin: "nav2_smac_planner/SmacPlannerHybrid"
      motion_model_for_search: "REEDS_SHEPP"
      minimum_turning_radius: 0.6
      max_planning_time: 7.0
      angle_quantization_bins: 64
      smoother:
        max_iterations: 2000
        w_smooth: 0.5
        w_data: 0.1
```

### 关键参数详解

| 参数 | 当前值 | 含义 | 调参建议 |
|------|--------|------|---------|
| `motion_model_for_search` | `REEDS_SHEPP` | Reeds-Shepp 曲线（前进+后退运动） | 差速车也可用 `DUBINS`（仅前进） |
| `minimum_turning_radius` | **0.6 m** | 最小转弯半径，需与车物理能力匹配 | 调小 → 路径更灵活但可能不真实；调大 → 路径更平滑 |
| `max_planning_time` | 7.0 秒 | 规划超时时间 | 增大 → 更复杂的路径也能找到；减小 → 快速返回次优路径 |
| `angle_quantization_bins` | 64 | 航向角离散化精度 | 增大 → 更精细但更慢 |
| **smoother.w_smooth** | **0.5** | 平滑权重 | **增大** → 路径更平滑；**减小** → 路径更保留原始形状 |
| **smoother.w_data** | **0.1** | 原始路径保留权重 | **增大** → 更贴墙；**减小** → 更远离障碍物 |
| `smoother.max_iterations` | 2000 | 平滑最大迭代 | 保持默认 |

### 路径平滑原理

```
w_smooth ↑ + w_data ↓ → 路径更平滑、更远离墙（代价：路径更长）
w_smooth ↓ + w_data ↑ → 路径更贴墙、更短（代价：不够平滑）
```

**环境狭窄**时：适当减小 `w_smooth`、增大 `w_data`，避免平滑把路径推出可行区域。

---

## 6. Behavior Server 行为服务器

处理特殊情况下的恢复行为（卡住时旋转、后退等）。

```yaml
behavior_server:
  ros__parameters:
    behavior_plugins: ["spin", "backup", "drive_on_heading", "wait"]
    global_frame: odom_combined
    robot_base_frame: base_footprint
    max_rotational_vel: 1.0
    rotational_acc_lim: 0.3
```

### 可用行为

| 行为 | 说明 |
|------|------|
| `spin` | 原地旋转（用于重新定位或调整方向） |
| `backup` | 后退（前方被堵时脱困） |
| `drive_on_heading` | 直线行驶（朝固定方向走一段） |
| `wait` | 等待 |

### 关键参数

| 参数 | 当前值 | 含义 | 调参建议 |
|------|--------|------|---------|
| `max_rotational_vel` | **1.0 rad/s** (~57°/s) | 最大旋转速度 | 减小 → 旋转更柔和；增大 → 转向更快 |
| `rotational_acc_lim` | **0.3 rad/s²** | 旋转加速度限制 | 增大 → 启停更干脆；减小 → 启停更柔和 |

---

## 7. Waypoint Follower 航点跟随器

配合 `nav2_waypoint_cycle` 包实现多点导航。

```yaml
waypoint_follower:
  ros__parameters:
    stop_on_failure: False
    waypoint_task_executor_plugin: "wait_at_waypoint"
    wait_at_waypoint:
      waypoint_pause_duration: 200  # 每点停留 (ms)
```

| 参数 | 当前值 | 含义 | 调参建议 |
|------|--------|------|---------|
| `stop_on_failure` | false | 一个航点失败后是否停止全部 | true → 严格模式；false → 容错模式 |
| `waypoint_pause_duration` | **200 ms** | 到达每个航点后的暂停时长 | 比赛需要停顿时调大（如 5000=5秒） |

---

## 8. Map Saver 地图保存

```yaml
map_saver:
  ros__parameters:
    save_map_timeout: 5.0
    free_thresh_default: 0.25
    occupied_thresh_default: 0.65
```

| 参数 | 含义 |
|------|------|
| `save_map_timeout` | 保存地图操作的超时时间（秒） |
| `free_thresh_default` | 像素值低于此阈值视为自由空间 |
| `occupied_thresh_default` | 像素值高于此阈值视为障碍物 |

---

## 9. 参数速查表

### 按问题定位

| 你遇到的现象 | 根因 | 改哪里 | 建议方向 |
|-------------|------|--------|---------|
| **左右晃动/S 形** | 前视距离(0.3m) < 转弯半径(0.6m) | `lookahead_dist` | 0.3 → **0.5~0.8** |
| **撞墙/创墙** | 碰撞检测关闭 | `use_collision_detection` | false → **true** |
| **撞墙/创墙** | 膨胀半径太小 | `inflation_radius` (局部/全局) | 0.25/0.15 → **0.5/0.4** |
| **撞墙/创墙** | 障碍物检测范围不足 | `obstacle_max_range` | 2.5 → **4.0** |
| **犹豫/走走停停** | `min_approach_linear_velocity` 比目标速度还高 | `min_approach_linear_velocity` | 0.5 → **0.15** |
| **过弯太冲** | 弯道减速生效慢 | `regulated_linear_scaling_min_speed` | 0.25 → **0.15** |
| **过弯太冲** | 速度太快 | `desired_linear_vel` | 0.33 → **0.25~0.28** |
| **路径贴墙** | 全局膨胀半径 0.15m 过小 | `global_costmap.inflation_layer.inflation_radius` | 0.15 → **0.4** |
| **路径贴墙** | 平滑参数导致路径靠边 | `smoother.w_data` | 0.1 → **0.05** |
| **大角度弯道犹豫** | 未启用原地旋转对准 | `use_rotate_to_heading` | false → **true** |
| **定位漂移** | AMCL 粒子数不足 | `max_particles` | 2000 → **3000** |

### 按模块速查

| 模块 | 参数 | 当前值 | 含义 |
|------|------|--------|------|
| AMCL | `max_particles` / `min_particles` | 2000 / 500 | 粒子滤波器范围 |
| BT | `goal_reached_tol` | 0.6 m | 到达容差 |
| 控制 | `desired_linear_vel` | 0.33 m/s | 目标速度 |
| 控制 | `lookahead_dist` | 0.3 m | 前视距离 |
| 控制 | `use_collision_detection` | false | 🚨 碰撞检测 |
| 规划 | `minimum_turning_radius` | 0.6 m | 最小转弯半径 |
| 规划 | `w_smooth` / `w_data` | 0.5 / 0.1 | 路径平滑 |
| 局部膨胀 | `inflation_radius` | 0.25 m | 局部安全余量 |
| 全局膨胀 | `inflation_radius` | 0.15 m | 全局安全余量 |
| 行为 | `max_rotational_vel` | 1.0 rad/s | 最大旋转速度 |
| 行为 | `rotational_acc_lim` | 0.3 rad/s² | 旋转加速度 |
| 航点 | `waypoint_pause_duration` | 200 ms | 航点停留 |

---

## 10. 运行时调参方法

### 修改单个参数测试（推荐）

```bash
ssh davinci-mini@192.168.5.100
source ~/racecar/install/setup.bash

# 查看当前值
ros2 param get /controller_server FollowPath.lookahead_dist

# 修改
ros2 param set /controller_server FollowPath.lookahead_dist 0.7
```

### 查看所有可调参数

```bash
ros2 param list /controller_server
ros2 param list /planner_server
ros2 param list /local_costmap
ros2 param list /global_costmap
```

### 可视化调参

```bash
ros2 run rqt_reconfigure rqt_reconfigure
```

### 永久修改

```bash
nano ~/racecar/src/racecar/config/nav.yaml
# 修改后重启 nav.sh 即可
# 如果只改配置文件不涉及代码，不需要 colcon build
```

### 调参原则

1. **一次只改 1~2 个参数**，测试效果后再改下一个
2. 先用 `ros2 param set` 运行时测试，确认有效再改配置文件
3. 优先解决最明显的症状（如先消除晃动，再看撞墙问题）
4. 记录每次修改前后的表现，方便回退

---

## 附录：配置链路一览

```
nav.yaml
 ├── amcl → 定位（我在哪？）
 ├── bt_navigator → 导航行为编排
 ├── controller_server → 局部路径跟踪（怎么走？）
 │    └── RegulatedPurePursuit → 速度指令
 ├── local_costmap → 实时避障
 ├── global_costmap → 全局规划背景
 ├── planner_server → 全局路径搜索（去哪条路？）
 │    └── SmacPlannerHybrid → 路径
 ├── behavior_server → 异常恢复
 ├── waypoint_follower → 多点导航
 └── map_saver → 地图保存
```

控制流：

```
目标点 → BT Navigator
         ├→ Planner Server (SmacPlannerHybrid) → 全局路径
         └→ Controller Server (RegulatedPurePursuit)
                 ↓ 结合局部代价地图
            /cmd_vel → go.py → /car_cmd_vel → racecar_driver_node → 底盘
```

---

> **参见**：[15-导航调参指南.md](15-导航调参指南.md) — 包含调参前/后完整对比方案和已知问题排障
