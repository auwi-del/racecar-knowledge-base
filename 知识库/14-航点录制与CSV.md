# 手动标记路径点与 CSV 航点导航

## 概述

系统提供了两套流程来录制和执行自定义路径点：

1. **`get.py`** — 在 RViz 中手动标记目标点，录制到 CSV 文件
2. **`go.py`** — 从 CSV 文件读取航点，通过 `NavigateThroughPoses` Action 执行

这与 `waypoint_cycle`（通过 `/clicked_point` 设置航点）是互补的方案。`go.py` 更灵活，可在执行时通过 `/cmd_vel` 干预控制。

## CSV 航点文件格式

航点文件位于 `~/racecar/src/racecar/scripts/` 目录下，格式为 CSV：

| 文件 | 路径 | 航点数量 |
|------|------|---------|
| 主文件 | `out_test.csv` | 21 个点 |
| 备份文件 | `out_test/out_test.csv` | 20 个点 |

每行格式：`x, y, orientation_z, orientation_w`

示例数据：
```
2.0495, -0.2543, -0.0222, 0.9998
3.7360, -0.7464, -0.1936, 0.9811
...
```

其中 x/y 是地图坐标系下的坐标（米），z/w 是朝向四元数。

## 完整流程：录制 + 执行

### 第1步：启动导航

```bash
ssh davinci-mini@192.168.5.100
bash ~/racecar/nav.sh
```

### 第2步：录制路径点

另开终端启动 `get.py`，它会订阅 `/goal_pose` 话题：

```bash
ssh davinci-mini@192.168.5.100
source ~/racecar/install/setup.bash
ros2 run racecar get
```

### 第3步：在 RViz 中标记路径点

在 RViz 中，点击 **"2D Nav Goal"** 按钮，依次在地图上点击目标点。每点击一个，`get.py` 自动录制航点到内存。

按下 **`f` 键** 将所有已录制的航点保存到 `out_test.csv`。

按 **`Ctrl+C`** 退出。

### 第4步：执行路径点导航

```bash
ssh davinci-mini@192.168.5.100
source ~/racecar/install/setup.bash
ros2 run racecar go
```

`go.py` 会：
1. 读取 CSV 中的全部航点
2. 通过 `navigate_through_poses` Action 一次性发送给 Nav2
3. 机器人沿路径依次访问每个航点
4. 到达最后一个点后停止

### 执行中的干预控制

`go.py` 订阅 `/cmd_vel`，转发到 `/car_cmd_vel`，所以运行期间可通过键盘遥控干预：

```bash
# 另开终端，随时发 Twist 指令干预
ros2 run racecar racecar_teleop
```

当距离目标 < 0.5m 时，`go.py` 自动发布停止命令完成该航点。

## 两个 CSV 文件说明

| 文件 | 用途 |
|------|------|
| `~/racecar/src/racecar/scripts/out_test.csv` | 主文件，`get.py` 默认保存位置，`go.py` 默认读取位置 |
| `~/racecar/src/racecar/scripts/out_test/out_test.csv` | 备份/历史航点文件 |

## 与 waypoint_cycle 的区别

| 特性 | waypoint_cycle | go.py + CSV |
|------|---------------|-------------|
| 航点来源 | RViz 实时点击 `/clicked_point` | 从 CSV 文件读取 |
| 执行方式 | 逐个发送 `/goal_pose` | 一次性 `NavigateThroughPoses` Action |
| 循环 | 自动循环 | 执行一次即停 |
| 持久化 | 重启丢失 | 保存到文件可复用 |
| 运行中干预 | 不支援 | 支持 `/cmd_vel` 干预 |

---

## 坐标匹配原理（PGM 地图 ↔ CSV 航点）

### 核心概念

CSV 中的航点坐标 (x, y) 是 **map 坐标系下的世界坐标（米）**，与 PGM 地图像素通过 YAML 元数据关联。

### 坐标转换公式

YAML 文件中的 `origin` 定义了**左下角像素中心**的世界坐标，`resolution` 定义每像素多少米：

```
world_x = origin_x + (col + 0.5) × resolution
world_y = origin_y + (height - 1 - row + 0.5) × resolution
```

逆变换（世界坐标 → 像素坐标）：

```
col = (world_x - origin_x) / resolution - 0.5
row = height - 1 - (world_y - origin_y) / resolution - 0.5
```

### 示例

对于 `ai_map.yaml`:
```yaml
resolution: 0.05        # 每像素 0.05 米
origin: [-10, -10, 0]   # 左下角像素中心的世界坐标
```
PGM 尺寸 992×384 像素：
- 地图覆盖世界范围：x[-10, 39.6], y[-10, 9.2]
- 航点 (1.96, -0.29) 在像素图中的位置：
  - col = (1.96 - (-10)) / 0.05 - 0.5 ≈ 238.7
  - row = 383 - (-0.29 - (-10)) / 0.05 - 0.5 ≈ 189.3

### RViz 中的坐标匹配

当用户在 RViz 中用 "2D Nav Goal" 点击地图时，RViz 内部执行上述逆变换，将像素点击转换为 map 坐标系下的世界坐标，然后通过 `/goal_pose` 话题发布（`frame_id: "map"`）。`get.py` 录制的就是这个 PoseStamped 里的 x/y/z/w。

这就解释了为什么：
- CSV 中的坐标值直接是米值（不是像素值）
- 在 Web 编辑器中导入 CSV 时，必须配合 YAML 才能正确将航点叠加到地图上
- YAML 的 origin 和 resolution 是关联 CSV ↔ PGM 的唯一桥梁

### Web Waypoint Editor 中的实现

桌面端 `waypoint-editor/index.html` 的 `drawMap()` 函数使用 `ctx.setTransform()` 实现像素→世界的映射：

```js
// 变换矩阵：PGM 像素 (col, row) → canvas 屏幕坐标
// a = scale * resolution       (x 方向缩放)
// d = -scale * resolution      (y 方向翻转)
// e = (origin_x + 0.5*res - cx) * scale + W/2
// f = (origin_y + (h-0.5)*res - cy) * scale + H/2
ctx.setTransform(a, 0, 0, d, e, f);
ctx.drawImage(mapImage, 0, 0);
```

这与 RViz 内部使用的坐标变换完全一致，保证了同一组 CSV 航点在 Web 编辑器和 RViz 中的显示位置完全对齐。
