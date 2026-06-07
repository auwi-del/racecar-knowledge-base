---
name: path-analysis-assistant
description: "Parse ROS2 rosbags to analyze robot navigation performance: extract /plan path, /odom_combined trajectory, /cmd_vel commands — evaluate path quality, tracking error, velocity response — suggest nav.yaml tuning. Also supports CSV path file analysis."
command: path-analysis
disable-model-invocation: true
---

## 任务

首选通过 **Python 库 `rosbags`** 解析 rosbag 文件，提取多话题数据进行全面的导航性能分析（路径质量、轨迹跟踪误差、速度响应、定位漂移）。同时保留 CSV 路径文件分析作为备选模式。

## 直接调用

通过 `/path-analysis` 命令调用。支持参数：

**主要模式（bag 解析）：**
- **bag**：指定 rosbag 目录/文件路径（如 `bags/nav_test_0/`，不提供则自动 SSH 搜索最新 bag）
- **topics**：要分析的话题列表（逗号分隔），默认自动检测
- **mode**：分析模式（见下文分析模式）

**备选模式（CSV 文件）：**
- **csv**：指定 CSV 文件路径（不提供则自动搜索）
- **mode**：分析模式（full | quick | compare）

### 分析模式

| mode 值 | 适用输入 | 说明 |
|:-------:|:--------:|:------|
| `full` | bag / csv | 完整分析报告（默认） |
| `quick` | bag / csv | 快速摘要 |
| `path` | bag 专用 | 仅解析 `/plan` 话题，输出路径质量分析 |
| `tracking` | bag 专用 | 规划路径 vs 实际轨迹的跟踪误差分析 |
| `velocity` | bag 专用 | 速度指令 vs 实际速度响应分析 |
| `compare` | csv 专用 | 多 CSV 文件对比分析 |

---

## 一、Rosbag 分析（主要方式）

### 1.1 环境准备

**无需 ROS2 环境**，使用纯 Python 库 `rosbags` 跨平台解析（Windows/Linux/macOS 均可）：

```bash
pip install rosbags
```

### 1.2 Bag 文件定位

如果用户指定了 `bag` 参数，直接使用该路径。

如果未指定，通过 SSH 在开发板上搜索最新 bag：

```bash
ssh davinci-mini@192.168.5.100 "ls -td ~/racecar/bags/*/ 2>/dev/null | head -1"
```

搜索到后用 `scp` 或 `rsync` 拉取到本地（bag 可能较大，建议用 rsync）：

```bash
rsync -avz davinci-mini@192.168.5.100:"远程路径/" ./local_bag/
```

### 1.3 使用 `rosbags` 库解析

```python
from rosbags.rosbag2 import Reader
from rosbags.serde import deserialize_cdr
from rosbags.typesys import get_types_from_msg, register_types
import numpy as np

# 方式一：自动检测类型
with Reader('path/to/bag') as reader:
    for connection, timestamp, rawdata in reader.messages():
        if connection.topic == '/plan':
            msg = deserialize_cdr(rawdata, connection.msgtype)
            # msg 为 Python 数据结构
            poses = msg['poses']  # list of PoseStamped
            for pose in poses:
                x = pose['pose']['position']['x']
                y = pose['pose']['position']['y']
```

### 1.4 可分析的话题与维度

| 话题 | 消息类型 | 分析维度 |
|:----:|:---------|:---------|
| `/plan` | `nav_msgs/msg/Path` | 规划路径质量（平滑度/曲折比/转弯半径） |
| `/odom_combined` | `nav_msgs/msg/Odometry` | 实际行驶轨迹、速度响应 |
| `/car_cmd_vel` | `geometry_msgs/msg/TwistStamped` | 下发的速度指令 |
| `/teleop_cmd_vel` | `geometry_msgs/msg/TwistStamped` | 键盘/脚本下发速度指令 |
| `/scan` | `sensor_msgs/msg/LaserScan` | 障碍物分布、通过性 |
| `/tf` | `tf2_msgs/msg/TFMessage` | 位姿变换时间线 |
| `/imu` | `sensor_msgs/msg/Imu` | 角速度/线加速度（抖动分析） |

### 1.5 分析脚本模板

以下 Python 脚本模板供 AI 在本地编写运行。可以用 `rosbags` 库完成所有解析，无需 ROS2 环境。

#### 1.5.1 提取规划路径（`/plan`）并分析路径质量

```python
import numpy as np
from rosbags.rosbag2 import Reader
from rosbags.serde import deserialize_cdr
import math

def get_msg_count(reader, topic):
    """获取话题的消息总数"""
    count = 0
    for conn, ts, raw in reader.messages():
        if conn.topic == topic:
            count += 1
    return count

def extract_plan_paths(bag_path):
    """从 bag 中提取所有 /plan 路径"""
    paths = []
    with Reader(bag_path) as reader:
        for connection, timestamp, rawdata in reader.messages():
            if connection.topic == '/plan':
                msg = deserialize_cdr(rawdata, connection.msgtype)
                poses = msg['poses']
                points = []
                for pose in poses:
                    p = pose['pose']['position']
                    points.append({
                        'x': p['x'], 'y': p['y'],
                        'stamp_nsec': pose['header']['stamp']['sec'] * 1e9
                                       + pose['header']['stamp']['nanosec']
                    })
                # 计算 segment_dist
                for i in range(len(points)):
                    if i == 0:
                        points[i]['segment_dist'] = 0.0
                    else:
                        dx = points[i]['x'] - points[i-1]['x']
                        dy = points[i]['y'] - points[i-1]['y']
                        points[i]['segment_dist'] = math.hypot(dx, dy)
                # 计算 yaw (朝向角)
                for i in range(len(points)):
                    if i < len(points) - 1:
                        dx = points[i+1]['x'] - points[i]['x']
                        dy = points[i+1]['y'] - points[i]['y']
                        yaw_rad = math.atan2(dy, dx)
                        points[i]['yaw_deg'] = math.degrees(yaw_rad) % 360
                    else:
                        points[i]['yaw_deg'] = points[i-1]['yaw_deg'] if i > 0 else 0
                paths.append({
                    'points': points,
                    'count': len(points),
                    'timestamp': timestamp,
                })
    return paths

def analyze_path_quality(paths):
    """分析路径质量指标（与 CSV 分析相同框架）"""
    for pi, path in enumerate(paths):
        pts = path['points']
        segs = [p['segment_dist'] for p in pts if p['segment_dist'] > 0]

        # 段间距变异系数
        if segs:
            mean_s = np.mean(segs)
            std_s = np.std(segs)
            seg_cv = std_s / mean_s if mean_s > 0 else 0
        else:
            seg_cv = 0

        # 总长
        total_length = sum(segs)

        # 起点终点直线距离
        dx = pts[-1]['x'] - pts[0]['x']
        dy = pts[-1]['y'] - pts[0]['y']
        straight_dist = math.hypot(dx, dy)
        detour_ratio = total_length / straight_dist if straight_dist > 0 else float('inf')

        # 角度变化
        max_angle_change = 0
        sharp_turns = 0
        for i in range(1, len(pts)):
            change = abs(pts[i]['yaw_deg'] - pts[i-1]['yaw_deg'])
            if change > 180:
                change = 360 - change
            if change > max_angle_change:
                max_angle_change = change
            if change > 15:
                sharp_turns += 1

        # 最小转弯半径
        min_turn_radius = float('inf')
        for i in range(1, len(pts)):
            angle_change_rad = abs(pts[i]['yaw_deg'] - pts[i-1]['yaw_deg'])
            if angle_change_rad > 180:
                angle_change_rad = 360 - angle_change_rad
            angle_change_rad = math.radians(angle_change_rad)
            if angle_change_rad > math.radians(1.0):
                radius = pts[i]['segment_dist'] / angle_change_rad
                if radius < min_turn_radius:
                    min_turn_radius = radius

        path['analysis'] = {
            'point_count': len(pts),
            'total_length_m': round(total_length, 3),
            'straight_dist_m': round(straight_dist, 3),
            'detour_ratio': round(detour_ratio, 2),
            'seg_consistency': round(seg_cv, 3),
            'max_angle_change_deg': round(max_angle_change, 1),
            'sharp_turn_count': sharp_turns,
            'min_turn_radius_m': round(min_turn_radius, 3) if min_turn_radius != float('inf') else 'N/A',
        }
    return paths
```

#### 1.5.2 提取实际轨迹（`/odom_combined`）

```python
def extract_trajectory(bag_path, topic='/odom_combined'):
    """从 bag 提取实际行驶轨迹（里程计数据）"""
    trajectory = []
    with Reader(bag_path) as reader:
        for connection, timestamp, rawdata in reader.messages():
            if connection.topic == topic:
                msg = deserialize_cdr(rawdata, connection.msgtype)
                pose = msg['pose']['pose']['position']
                twist = msg['twist']['twist']
                trajectory.append({
                    'stamp_nsec': timestamp,
                    'x': pose['x'],
                    'y': pose['y'],
                    'vx': twist['linear']['x'],
                    'vy': twist['linear']['y'],
                    'wz': twist['angular']['z'],
                    # 从 orientation 提取 yaw
                    'orientation': msg['pose']['pose']['orientation'],
                })
    # 计算逐点的速度、加速度
    for i in range(len(trajectory)):
        if i > 0:
            dt = (trajectory[i]['stamp_nsec']
                  - trajectory[i-1]['stamp_nsec']) / 1e9
            if dt > 0:
                dx = trajectory[i]['x'] - trajectory[i-1]['x']
                dy = trajectory[i]['y'] - trajectory[i-1]['y']
                trajectory[i]['v_linear'] = math.hypot(dx, dy) / dt
            else:
                trajectory[i]['v_linear'] = 0
        else:
            trajectory[i]['v_linear'] = 0
    return trajectory
```

#### 1.5.3 提取速度指令（`/car_cmd_vel` / `teleop_cmd_vel`）

```python
def extract_cmd_vel(bag_path, topic='/car_cmd_vel'):
    """从 bag 提取速度指令"""
    commands = []
    with Reader(bag_path) as reader:
        for connection, timestamp, rawdata in reader.messages():
            if connection.topic == topic:
                msg = deserialize_cdr(rawdata, connection.msgtype)
                commands.append({
                    'stamp_nsec': timestamp,
                    'vx': msg['twist']['linear']['x'],
                    'wz': msg['twist']['angular']['z'],
                })
    return commands
```

### 1.6 核心分析维度

#### 维度 A：路径质量（Plan Quality）

| 指标 | 计算方法 | 良好 | 警告 | 异常 |
|:----:|:---------|:----:|:----:|:----:|
| 段间距变异系数 | segment_dist std/mean | < 0.3 | 0.3~0.5 | > 0.5 |
| 最大角度变化 | max(yaw_diff) 处理 360°绕越 | < 5° | 5°~15° | > 15° |
| 最小转弯半径 | seg_dist/angle_change_rad | > 0.6m | 0.3~0.6m | < 0.3m |
| 曲折比 | 总长/直线距离 | < 1.2x | 1.2x~1.5x | > 1.5x |

#### 维度 B：轨迹跟踪误差（Tracking Error）

将规划路径（`/plan`）与实际轨迹（`/odom_combined`）对齐比较：

| 指标 | 计算方法 | 说明 |
|:----:|:---------|:-----|
| 横向误差 | 实际点到最近规划路径段的垂直距离 | 均值 > 0.15m 说明跟踪差 |
| 航向误差 | 实际朝向与路径朝向的差值 | 均值 > 10° 说明转角响应慢 |
| 滞后时间 | 实际位置相对规划位置的延迟 | > 0.5s 说明控制器响应慢 |
| 终点误差 | 实际终点与规划终点的距离 | > 0.2m 说明定位漂移 |

```python
def compute_tracking_error(planned_path, actual_trajectory):
    """
    计算规划路径 vs 实际轨迹的跟踪误差
    planned_path: extract_plan_paths() 返回的单条路径
    actual_trajectory: extract_trajectory() 返回的轨迹
    """
    import numpy as np
    from scipy.spatial import KDTree  # 可选，用于最近点查找

    plan_pts = np.array([[p['x'], p['y']] for p in planned_path['points']])
    actual_pts = np.array([[p['x'], p['y']] for p in actual_trajectory])

    # 对每个实际点，找最近路径点
    tree = KDTree(plan_pts)
    distances, indices = tree.query(actual_pts)

    # 横向误差统计
    cross_track_error = {
        'mean_m': float(np.mean(distances)),
        'max_m': float(np.max(distances)),
        'std_m': float(np.std(distances)),
        'rms_m': float(np.sqrt(np.mean(distances**2))),
    }

    # 终点误差
    plan_end = plan_pts[-1]
    actual_end = actual_pts[-1]
    end_error = float(np.linalg.norm(actual_end - plan_end))

    return {
        'cross_track_error': cross_track_error,
        'end_position_error_m': round(end_error, 3),
        'tracking_quality': 'good' if cross_track_error['mean_m'] < 0.15
            else ('fair' if cross_track_error['mean_m'] < 0.3 else 'poor'),
    }
```

#### 维度 C：速度响应分析（Velocity Response）

对比速度指令与里程计反馈的速度：

| 指标 | 计算方法 | 说明 |
|:----:|:---------|:-----|
| 速度 RMS 误差 | cmd_vel vx 与 odom vx 的 RMS 差 | > 0.2m/s 说明速度控制不准 |
| 响应延迟 | 速度指令与速度响应的互相关峰值偏移 | 可通过时间戳对齐估算 |
| 角速度跟踪 | cmd_vel wz 与 odom wz 的误差 | 角速度延迟导致转弯 overshoot |
| 抖动频率 | 速度信号的功率谱峰值 | 高频抖动说明 PID 振荡 |

```python
def compute_tracking_error_from_topics(bag_path, plan_topic='/plan',
                                       odom_topic='/odom_combined',
                                       cmd_topic='/car_cmd_vel'):
    """综合计算跟踪误差（使用 bag 话题而非预处理数据）"""
    # 提取各话题数据
    paths = extract_plan_paths(bag_path)  # /plan
    trajectory = extract_trajectory(bag_path, odom_topic)  # odometry
    commands = extract_cmd_vel(bag_path, cmd_topic)  # cmd_vel

    # 仅取规划路径中的第一条
    if not paths:
        return {'error': 'bag 中无 /plan 话题'}

    plan = paths[0]

    # 维度 A：路径质量
    quality = plan.get('analysis', {})

    # 维度 B：跟踪误差
    tracking = compute_tracking_error(plan, trajectory)

    # 维度 C：速度响应
    if commands and trajectory:
        # 对齐时间戳，计算速度跟踪误差
        cmd_times = np.array([c['stamp_nsec'] for c in commands])
        odom_times = np.array([o['stamp_nsec'] for o in trajectory])

        # 找最近的 odom 点匹配每个 cmd
        vel_errors = []
        for cmd in commands:
            time_diff = np.abs(odom_times - cmd['stamp_nsec'])
            nearest_idx = np.argmin(time_diff)
            if time_diff[nearest_idx] < 0.1 * 1e9:  # 100ms 以内
                vel_errors.append(abs(cmd['vx'] - trajectory[nearest_idx]['vx']))

        vel_rms = np.sqrt(np.mean(np.array(vel_errors)**2)) if vel_errors else None
    else:
        vel_rms = None

    return {
        'path_quality': quality,
        'tracking': tracking,
        'velocity_rms_error': round(vel_rms, 3) if vel_rms else 'N/A',
        'diagnosis': [],
        'suggestions': [],
    }
```

---

## 二、CSV 文件分析（备选方式）

当用户提供 CSV 文件或指定 `csv` 参数时，沿用原有的CSV分析流程（保持不变）：

### CSV 格式

文件位于 `~/racecar/path_records/plan_*.csv`，元数据 `#` 头 + 数据列：

| 列 | 说明 |
|:--:|:-----|
| `point_id` | 路径点序号 |
| `x, y` | 地图坐标（米）|
| `yaw_deg` | 朝向角（0~360°）|
| `segment_dist` | 到上一点间距（米）|

### CSV 分析框架

同 [维度 A：路径质量](#%E7%BB%B4%E5%BA%A6-a%EF%BC%9A%E8%B7%AF%E5%BE%84%E8%B4%A8%E9%87%8Fplan-quality) 的 4 项指标。

---

## 三、典型问题诊断对照表

| 症状 | 诊断 | 应调整的参数 |
|:----|:-----|:-------------|
| /plan 路径左右锯齿 / S 形 | 前视距离太小 | `controller_server.FollowPath.lookahead_dist` ↑ |
| 跟踪误差偏大（cross_track > 0.15m） | 控制器跟踪不足 | `controller_server.FollowPath.desired_linear_vel` ↓ 或 `max_angular_vel` ↑ |
| 速度指令与实际速度 RMS 差 > 0.2m/s | 加减速限制太紧 | `controller_server.FollowPath.max_linear_accel/decel` ↑ |
| 路径偏地图边缘 / 距障碍物近 | 膨胀半径不足 | `costmap.inflation_radius` ↑ |
| 曲折比 > 1.5 | 代价惩罚偏低 | `planner_server.GridBased.cost_penalty` ↑ |
| yaw_deg 突变 > 15° 或角速度跟踪差 | 转弯半径约束或 rotate_to_heading | `minimum_turning_radius` / `use_rotate_to_heading` |
| odom_combined 轨迹有突然跳跃 | 定位漂移（AMCL 或 EKF） | `amcl` 参数或 `ekf` 协方差调整 |
| 实际速度响应明显滞后于指令 | 机械/电机响应慢 | 检查下位机 PID 或电池电量 |

---

## 四、分析报告模板

### 4.1 完整报告（mode=full, 输入为 bag）

```
═══════════════════════════════════════════
🗺️  导航性能分析报告（Rosbag）
   文件: nav_test_0/
═══════════════════════════════════════════

📋 Bag 基本信息
  话题统计: /plan (N条) /odom_combined (N条) /car_cmd_vel (N条)
  时长: XX.Xs | 消息总数: XXXX

📊 路径质量（/plan）
  点数: N | 总长: X.XXm
  段间距一致性: X.XXX (良好/⚠️/❌)
  最大角度变化: X.X°
  急弯数量: N | 最小转弯半径: X.XXm
  曲折比: X.XXx

📊 轨迹跟踪误差（计划 vs 实际）
  横向误差 RMS: X.XXXm
  横向误差 均值: X.XXXm | 最大: X.XXXm
  终点误差: X.XXm
  跟踪质量: ✅ 良好 / ⚠️ 一般 / ❌ 差

📊 速度响应
  速度 RMS 误差: X.XXX m/s
  备注: 有无明显延迟/抖动

🔍 诊断结论
  ✅ 逐项列出正常项
  ⚠️ 逐项列出警告项
  ❌ 逐项列出异常项

🔧 调参建议（按优先级）
  1. controller_server.FollowPath.lookahead_dist: 0.3 → 0.7
     说明：路径有锯齿，增大前视距离平滑路径

📝 备注
═══════════════════════════════════════════
```

### 4.2 快速摘要（mode=quick）

```
═══════════════════════════════════════════
🗺️  导航性能快速摘要
═══════════════════════════════════════════
Bag: nav_test_0/ | 时长: XXs
✅ 路径平滑 | ⚠️ 跟踪误差 0.18m | ❌ 无
🔧 建议：增大 lookahead_dist 至 0.7
═══════════════════════════════════════════
```

### 4.3 CSV 模式报告

同原有模板不变。

---

## 五、多 bag / 多 csv 对比分析

当传入多个 bag 或多个 CSV 文件时（`mode=compare`），对比分析：

| 对比维度 | 分析内容 |
|:---------|:---------|
| 路径质量趋势 | 曲折比/一致性/急弯数量是否随赛程变化 |
| 跟踪误差趋势 | 横向误差是否逐渐增大（定位漂移） |
| 速度响应趋势 | 响应延迟是否增大（电池衰减） |
| 区域分析 | 特定位置是否反复出现同样问题（地图质量） |

---

## 六、注意事项

- **`rosbags` 库是跨平台的纯 Python 库**，本地 Windows 环境可直接 `pip install rosbags` 使用，无需 ROS2 环境
- Bag 文件可能较大，建议用 `rsync` 拉取而非 `scp`
- 本 skill 对应的采集工具详见 `rosbag-recorder` skill
- CSV 路径分析作为备选保留，完整指标和诊断逻辑与 bag 模式中的路径质量分析一致
- 如果 bag 中缺少 `/plan` 话题，自动降级为仅分析实际轨迹（`/odom_combined`）和速度响应
- 轨迹跟踪误差分析要求 bag 中同时包含 `/plan` 和里程计话题（`/odom_combined` 或 `/odom`），若缺少其中之一则跳过该维度
