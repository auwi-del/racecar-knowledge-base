# CSV 航点自动停止功能（停止 3 秒 + 自动恢复）

## 概述

小车在多点导航时，到达某些航点后自动停止指定时长（例如 3 秒），然后自动继续前往下一个航点。此功能由 `go.py` 配合 CSV 文件的第 5 列 `stop_time` 实现。

与 `nav2_waypoint_cycle`（RViz 手动点选）不同，这套方案基于 CSV 文件预定义航点，适合重复执行固定路线的场景（如比赛路线）。

## 涉及的文件

| 文件 | 路径 | 角色 |
|------|------|------|
| `go.py` | `~/racecar/src/racecar/scripts/go.py` | **核心逻辑**：读取 CSV、逐点导航、停止计时、自动恢复 |
| `out_test.csv` | `~/racecar/src/racecar/scripts/out_test.csv` | **航点数据**：18 个航点，其中 3 个带 stop_time |
| `get.py` | `~/racecar/src/racecar/scripts/get.py` | 录制工具：在 RViz 中标记航点并保存为 CSV |
| `nav.sh` | `~/racecar/nav.sh` | 启动脚本：启动底盘 + 传感器 + Nav2（不含 go.py） |
| `nav.yaml` | `~/racecar/src/racecar/config/nav.yaml` | Nav2 参数：速度、容差、控制器等 |
| `Run_nav.launch.py` | `~/racecar/src/racecar/launch/Run_nav.launch.py` | 启动 Nav2 全套 + waypoint_cycle |

> **重要区分**：`nav.sh` + `waypoint_cycle` 是"RViz 手动点选"方案；`go.py` + CSV 是"预制航点自动执行"方案，二者**互斥**，运行 `go.py` 前需确保 `nav.sh` 已启动 Nav2，但不需要 `waypoint_cycle` 运行。

## 文件协同工作流程

### 整体流程

```
         ┌─────────────────────────────────────────────┐
         │            nav.sh (启动基础系统)               │
         │  Run_car.launch.py → 底盘 + LiDAR + IMU + EKF │
         │  Run_nav.launch.py → Nav2 (AMCL/planner/... ) │
         └────────────────────┬────────────────────────┘
                              │ Nav2 就绪
                              ▼
         ┌─────────────────────────────────────────────┐
         │        go.py (单独启动，独立终端)               │
         │                                              │
         │  1. 读取 out_test.csv → 加载 18 个航点        │
         │  2. 逐个发送 NavigateToPose Action Goal       │
         │  3. 每个点到达后：                             │
         │     ├─ stop_time=0 → 立即前往下一个            │
         │     └─ stop_time>0 → 停指定秒数后再继续         │
         └─────────────────────────────────────────────┘
```

### `go.py` 内部状态机

```
         ┌──────────────┐
         │ 读取 CSV 航点   │
         └──────┬───────┘
                ▼
         ┌──────────────┐
         │ 发送第 N 个目标  │◄────────────────────┐
         │ (NavigateToPose)│                     │
         └──────┬───────┘                      │
                ▼                               │
         ┌──────────────────┐                   │
         │ 等待 Nav2 执行结果  │                   │
         │                   │                   │
         │ 反馈回调：          │                   │
         │  distance<0.5m     │                   │
         │  → 发零速度命令      │                   │
         └──────┬───────┘                      │
                ▼                               │
         ┌──────────────────┐                   │
         │ 到达航点          │                   │
         │ get_result_callback│                   │
         └──────┬───────┘                      │
                ▼                               │
         ┌──────────────────┐                   │
         │ 检查 stop_time    │                   │
         │ 第 N 个点          │                   │
         ├─────────┬────────┤                   │
         │ =0       │ >0    │                   │
         ▼         ▼        │                   │
         ┌──┐   ┌──────────────┐                │
         │  │   │ 发零速度 → 停止  │              │
         │  │   │ 创建定时器     │               │
         │  │   │ sleep(stop_time)│              │
         │  │   └──────┬───────┘               │
         │  │          ▼ stop_time 到           │
         │  │   ┌──────────────┐               │
         │  │   │ 取消定时器     │               │
         └──┼───┤ 前往下一航点 ──┼───────────────┘
            │   └──────────────┘
            ▼
         ┌──────────────┐
         │ 所有航点完成     │
         │ spin 结束      │
         └──────────────┘
```

## 核心代码详解

### 1. CSV 格式：第 5 列 = stop_time

文件：`~/racecar/src/racecar/scripts/out_test.csv`

```
x, y, orientation_z, orientation_w, [stop_time_seconds]
```

示例（第 2、8、16 行带 stop_time=3）：

```
2.0495, -0.2543, -0.0222, 0.9998               ← stop=0，不停
3.1268, -0.5585, -0.1936, 0.9811, 3            ← 到达后停 3 秒
5.6905, -1.5733, -0.2134, 0.9770               ← 不停
...
11.8980, -2.0346, 0.0970, 0.9953, 3            ← 停 3 秒
...
4.6505, -1.0992, -0.9846, 0.1750, 3            ← 停 3 秒
...
-0.1825, -0.8500, 0.0072, 0.99997              ← 不停（回到起点附近，共 18 个点）
```

### 2. CSV 读取函数（`go.py`）

```python
def read_waypoints_from_csv(filename):
    waypoints = []
    with open(filename, "r") as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) >= 4:
                # 第5列可选，不存在或为空则 stop_time=0
                stop_time = float(row[4]) if len(row) >= 5 and row[4].strip() else 0.0
                waypoint = {
                    "x": float(row[0]),
                    "y": float(row[1]),
                    "z": float(row[2]),
                    "w": float(row[3]),
                    "stop_time": stop_time   # ← 停止时长（秒）
                }
                waypoints.append(waypoint)
    return waypoints
```

### 3. 导航执行及停止逻辑（`go.py`）

使用 Nav2 `NavigateToPose` Action（逐个发送，非 `NavigateThroughPoses`）：

**到达回调 → 触发停止：**

```python
def get_result_callback(self, future):
    self.get_logger().info("Waypoint #" + str(self.current_idx) + " completed")
    self.navigating = False

    # 读取当前航点的 stop_time
    stop_time = self.waypoints[self.current_idx].get("stop_time", 0.0)
    self.current_idx += 1

    if stop_time > 0:
        # === 停止逻辑 ===
        self.get_logger().info("Stopping for " + str(stop_time) + " seconds...")
        twist = Twist()                        # 零速度命令
        self.car_cmd_vel_pub.publish(twist)    # 直接发到底盘驱动
        # 创建一次性定时器，stop_time 秒后恢复
        self._stop_timer = self.create_timer(stop_time, self.stop_timer_callback)
    else:
        self.start_navigation()  # 不停止，直接下一个
```

**停止结束 → 恢复导航：**

```python
def stop_timer_callback(self):
    self.get_logger().info("Stop finished, continuing to next waypoint")
    if self._stop_timer:
        self._stop_timer.cancel()
        self._stop_timer = None
    self.start_navigation()  # 继续发送下一个航点
```

### 4. 提前减速（到达前的缓冲）

当导航反馈 `distance_remaining < 0.5m` 时，主动发零速度命令，确保小车精准停在目标点：

```python
def feedback_callback(self, feedback_msg):
    distance = feedback_msg.feedback.distance_remaining
    if distance > 0 and distance < 0.5:
        twist = Twist()                       # 零速度
        self.car_cmd_vel_pub.publish(twist)   # 直接到底盘
```

### 5. 正常导航时的转发控制

小车正常行驶时，`/cmd_vel`（Nav2 控制器输出）通过 `go.py` 转发到 `/car_cmd_vel`（底盘驱动输入），`go.py` 在中间起到"门控"作用：

```python
def cmd_vel_callback(self, msg):
    if self.navigating:          # 只有导航中才转发
        self.car_cmd_vel_pub.publish(msg)
```

停止时 `self.navigating = False`，任何 Nav2 发出的速度都被阻断，同时 `go.py` 自己发布零速度，确保小车不动。

## 启动方法

### 完整启动步骤

```bash
# 终端 1：启动底盘 + 传感器 + Nav2
ssh davinci-mini@192.168.5.100
bash ~/racecar/nav.sh

# 终端 2：等待 nav.sh 就绪后，运行 CSV 航点导航
ssh davinci-mini@192.168.5.100
source ~/racecar/install/setup.bash
ros2 run racecar go
```

`go.py` 启动后会自动：
1. 读取 `out_test.csv`
2. 打印加载的航点数量和每个点的坐标
3. 开始逐点导航
4. 遇到 `stop_time>0` 的航点自动停止并计时
5. 停止结束后自动前往下一航点

## CSV 文件的 stop_time 配置说明

### 添加/修改停止时间

编辑 `out_test.csv`，在需要停车的航点行末尾添加第 5 列：

```csv
# 不停车：4 列
x, y, z, w

# 停 3 秒：5 列
x, y, z, w, 3

# 停 5 秒
x, y, z, w, 5
```

`out_test.csv` 当前有 18 个航点，其中 3 个配置了 `stop_time=3`（第 2、8、16 行）。

### 使用 get.py 录制后手动添加

`get.py` 录制时只保存 4 列（x/y/z/w），如需 stop_time 需手动编辑添加第 5 列。

## 与 `waypoint_cycle` 的对比

| 特性 | waypoint_cycle | go.py + CSV |
|------|---------------|-------------|
| 导航动作 | `/goal_pose` 话题 | `NavigateToPose` Action |
| 航点来源 | RViz 实时点击 | CSV 文件预定义 |
| stop_time 停等 | 不支持 | 支持（第 5 列） |
| 自动恢复 | 不支持 | 支持 |
| 循环 | 全部到达后自动循环 | 全部到达后停止 |
| 状态反馈 | `/action/status` | Action 结果回调 |
| 速度门控 | 无 | 有（转发/阻断控制） |
| 适用场景 | 探索/调试 | 比赛/固定路线 |

## 关键 Nav2 参数影响

`nav.yaml` 中以下参数影响停车的精度和表现：

| 参数 | 值 | 影响 |
|------|-----|------|
| `goal_reached_tol` | 0.6 m | Nav2 判断"到达"的容差 |
| `xy_goal_tolerance` | 0.6 m | 控制器目标容差 |
| `min_approach_linear_velocity` | 0.15 m/s | 接近目标时的最低速度 |
| `approach_velocity_scaling_dist` | 1.5 m | 开始减速的距离 |
| `desired_linear_vel` | 0.33 m/s | 巡航速度 |
