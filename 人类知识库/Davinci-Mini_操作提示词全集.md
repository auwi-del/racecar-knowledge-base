# Davinci-Mini ROS2 小车 — 操作提示词全集

> 整理自本地知识库 (`C:\Users\LX\Desktop\文档 - 机器人比赛\`) + 操作截图
> 最后更新：2026-06-05


##启动
bash ~/racecar/car.sh
或
cd racecar
bash car.sh

## 键盘控制
新建终端并输入
ros2 run racecar racecar_teleop.py    # 键盘控制小车
## 地图构建
一终端：
cd racecar
bash gmapping.sh
二终端：
ros2 run racecar racecar_teleop.py
键盘控制关闭：
cd racecar
bash save.sh

## 单点导航（校准地图，一般不用）
cd racecar
bash nav_one.sh

## 多点导航
一终端：
cd racecar
bash nav.sh
或
bash ~/racecar/car.sh
二终端：
ros2 run racecar get.py   #（先不运行）膨胀后运行
标点，标点后 f 保存
文件可在路径/racecar/src/racerar/script/查看
        Ctrl+c
        pkill-9-f”ros-args”
关闭所有终端

##运行多点导航
ros2 run racecar go.py（先不运行）膨胀后运行

Claude提示词以及skill
claude
/connect-davinci     (连接小车）
扫描当前目录下git仓库，提交git仓库  /racecar-git
封装成skill
/csv-manager 下载（将改完的点下载到桌面文件夹里）
/csv-manager 上传+桌面文件地址    （将改完的点存到开发板里）

---

## 目录

1. [连接与准备](#1-连接与准备)
2. [启动机器人](#2-启动机器人)
3. [键盘控制与遥控](#3-键盘控制与遥控)
4. [地图构建（SLAM）](#4-地图构建slam)
5. [导航启动与操作](#5-导航启动与操作)
6. [多点导航（CSV 航点）](#6-多点导航csv-航点)
7. [导航调参指南](#7-导航调参指南)
8. [CSV 航点自动停止功能](#8-csv-航点自动停止功能)
9. [地图文件管理](#9-地图文件管理)
10. [Claude 技能速查表](#10-claude-技能速查表)
11. [调试命令速查](#11-调试命令速查)

---

## 1. 连接与准备

### 硬件连接

| 项目 | 说明 |
|------|------|
| 开发板 IP | `192.168.5.100` |
| 本机推荐 IP | `192.168.5.2`（以太网网卡手动设置） |
| 连接方式 | 以太网直连或同一交换机 |
| SSH 认证 | 密钥认证（免密） |

### 检查网络连通性

```bash
ping 192.168.5.100
```

### SSH 连接

```bash
ssh davinci-mini@192.168.5.100
```

### 初始化（仅首次或更换硬件后）

```bash
cd ~/racecar
bash racecar_init.sh   # 需要 sudo 权限
```

---

## 2. 启动机器人

### 仅底盘 + 传感器模式（用于遥控/循迹）

```bash
bash ~/racecar/car.sh
```

启动内容：EKF 里程计融合、LiDAR 激光雷达、IMU、编码器、底盘驱动、RViz

### 底盘 + 导航模式（用于自主导航）

```bash
bash ~/racecar/nav.sh
```

启动流程：
1. `Run_car.launch.py` — 底盘 + 传感器
2. 等待 10 秒
3. `Run_nav.launch.py` — Nav2 全套（AMCL + planner + controller + waypoint_cycle）

### 底盘 + Gmapping SLAM（建图模式）

```bash
bash ~/racecar/gmapping.sh
```

### 停止系统

按 `Ctrl+C` 即可终止所有后台进程。脚本中的 `trap terminate SIGINT` 会依次清理。

---

## 3. 键盘控制与遥控

```bash
# 新开一个 SSH 终端
ssh davinci-mini@192.168.5.100
source ~/racecar/install/setup.bash
ros2 run racecar racecar_teleop
```

或简写（无需手动 source，因为 `ros2` 环境在 `.bashrc` 中已加载）：

```bash
ros2 run racecar racecar_teleop
```

---

## 4. 地图构建（SLAM）

### 建图流程

```bash
# 终端 1：启动 SLAM
bash ~/racecar/gmapping.sh

# 终端 2：启动键盘控制
ros2 run racecar racecar_teleop
```

操作步骤：
1. 遥控机器人缓慢走遍整个区域
2. 确保回环闭合（走一圈回到起点附近区域）
3. RViz 会自动打开，添加 `/map` 话题查看建图进度

### 保存地图

```bash
bash ~/racecar/save.sh
```

保存位置：`~/racecar/src/racecar/map/`，生成：
- `ai_map.yaml` — 地图元数据
- `ai_map.pgm` — 灰度图像

手动保存可指定路径：
```bash
ros2 run nav2_map_server map_saver_cli -f ~/racecar/src/racecar/map/my_map
```

---

## 5. 导航启动与操作

### 启动导航

```bash
# 单终端即可
bash ~/racecar/nav.sh
```

`nav.sh` 会自动设置初始位姿（默认 `[0, 0, 0]`），无需手动设置。

### 导航操作方法

| 方法 | 操作 | 说明 |
|------|------|------|
| RViz 2D Nav Goal | 点击按钮 → 点击地图目标点 | 单点导航 |
| Publish Point | 点击按钮 → 点击多个航点 | 航点循环（自动逐个执行） |
| 命令行 | `ros2 topic pub /goal_pose ...` | 编程控制 |

### 单点导航（校准地图用，一般不常用）

```bash
bash ~/racecar/nav_one.sh
```

---

## 6. 多点导航（CSV 航点）

### 方案一：RViz 手动点选（waypoint_cycle）

在 `nav.sh` 启动后：
1. 在 RViz 中点击 **Publish Point** 按钮
2. 在地图上依次点击多个航点（显示带编号的箭头）
3. 自动逐个执行，完成后从头循环

### 方案二：CSV 预制航点（get.py → go.py）

适合重复执行固定路线（如比赛路线）。

#### 录制航点

```bash
# 终端 1：启动导航
bash ~/racecar/nav.sh

# 终端 2：启动录制
source ~/racecar/install/setup.bash
ros2 run racecar get
```

在 RViz 中使用 **2D Nav Goal** 依次点击目标点。每点一个自动录制。
按 **f 键** 保存到 `out_test.csv`，按 `Ctrl+C` 退出。

#### 执行航点导航

```bash
# 确保 nav.sh 已启动
# 新终端执行：
source ~/racecar/install/setup.bash
ros2 run racecar go
```

`go.py` 启动后自动读取 `out_test.csv`，逐个导航到每个航点。

### 两个 CSV 文件说明

| 文件 | 路径 | 用途 |
|------|------|------|
| 主文件 | `~/racecar/src/racecar/scripts/out_test.csv` | `get.py` 默认保存，`go.py` 默认读取 |
| 备份 | `~/racecar/src/racecar/scripts/out_test/out_test.csv` | 备份/历史航点 |

CSV 格式：`x, y, orientation_z, orientation_w[, stop_time]`

---

## 7. 导航调参指南

> 配置文件路径：`~/racecar/src/racecar/config/nav.yaml`
> 修改后重启 `nav.sh` 生效，**不需要 colcon build**

### 最核心要改的 4 个参数

| # | 行号 | 参数 | 旧值 → 新值 | 作用 |
|---|------|------|-------------|------|
| 1 | 121 | `use_collision_detection` | `false → true` | 开启碰撞检测 |
| 2 | 123 | `max_allowed_time_to_collision_up_to_carrot` | `1.0 → 2.0` | 留足反应时间 |
| 3 | 167 | 局部 `inflation_radius` | `0.25 → 0.5` | 局部膨胀半径 |
| 4 | 230 | 全局 `inflation_radius` | `0.15 → 0.4` | 全局膨胀半径 |

### 完整调整方案（8 个参数）

#### 一、前视距离（解决左右晃动）

```yaml
controller_server.FollowPath:
  lookahead_dist: 0.7               # 0.3 → 0.7
  min_lookahead_dist: 0.5           # 0.3 → 0.5
  max_lookahead_dist: 1.0           # 0.6 → 1.0
```

#### 二、开启碰撞检测（防止撞墙）

```yaml
use_collision_detection: true                    # false → true
max_allowed_time_to_collision_up_to_carrot: 2.0  # 新增
```

#### 三、膨胀半径（给墙壁更多缓冲）

```yaml
global_costmap.inflation_layer:
  inflation_radius: 0.4              # 0.15 → 0.4

local_costmap.inflation_layer:
  inflation_radius: 0.5              # 0.25 → 0.5
```

#### 四、修复减速逻辑矛盾（解决走走停停）

```yaml
min_approach_linear_velocity: 0.15   # 0.5 → 0.15
```

### 运行时临时调参测试（不重启）

```bash
# 查看当前值
ros2 param get /controller_server FollowPath.lookahead_dist

# 修改
ros2 param set /controller_server FollowPath.lookahead_dist 0.7
ros2 param set /controller_server FollowPath.min_lookahead_dist 0.5
ros2 param set /controller_server FollowPath.max_lookahead_dist 1.0
```

测试满意后再永久写入 `nav.yaml`。

### 永久修改配置文件

```bash
nano ~/racecar/src/racecar/config/nav.yaml
```

找到 `controller_server → FollowPath` 段修改对应值，保存后重启 `nav.sh`。

### 二级调整（进一步优化）

```yaml
# 降低速度
controller_server.FollowPath.desired_linear_vel: 0.28  # 0.33 →

# 增加规划器平滑
planner_server.GridBased.smoother:
  w_smooth: 0.5 → 0.7
  w_data: 0.1 → 0.05

# 障碍物代价权重
planner_server.GridBased.cost_penalty: 1.7 → 2.5
planner_server.GridBased.cost_travel_multiplier: 2.0 → 3.0
```

### 参数速查表

| 想解决什么 | 改哪里 | 参数 | 方向 |
|-----------|--------|------|------|
| 左右晃动 | controller_server | lookahead_dist | 增大 |
| 撞墙 | controller_server | use_collision_detection | true |
| 撞墙 | local_costmap | inflation_radius | 增大 |
| 撞墙 | global_costmap | inflation_radius | 增大 |
| 犹豫/走走停停 | controller_server | min_approach_linear_velocity | 减小 |
| 过弯太冲 | controller_server | desired_linear_vel | 减小 |
| 路径太贴墙 | planner_server | cost_penalty | 增大 |
| 路径不平滑 | planner_server.smoother | w_smooth | 增大 |

---

## 8. CSV 航点自动停止功能

### 概述

到达某些航点后自动停止指定秒数，然后自动继续前往下一航点。由 `go.py` + CSV 第 5 列实现。

### CSV 格式

```csv
x, y, orientation_z, orientation_w, [stop_time_seconds]

# 示例：第 2 个点停 3 秒
3.1268, -0.5585, -0.1936, 0.9811, 3
```

不指定第 5 列或为 0 则不停车。

### 当前配置

`out_test.csv` 有 18 个航点，其中 3 个配置了 `stop_time=3`。

### 添加/修改停止时间

编辑 `~/racecar/src/racecar/scripts/out_test.csv`，在需要停车的航点行末尾添加第 5 列：

```csv
# 不停车：4 列
x, y, z, w

# 停 3 秒：5 列
x, y, z, w, 3
```

---

## 9. 地图文件管理

### 板上的地图位置

| 文件 | 路径 |
|------|------|
| 地图图像 | `~/racecar/src/racecar/map/ai_map.pgm` |
| 地图元数据 | `~/racecar/src/racecar/map/ai_map.yaml` |

### 本地桌面已有备份

| 文件 | 路径 |
|------|------|
| 地图图像 | `C:\Users\LX\Desktop\保存的点位\0602-170853\ai_map.pgm` |
| 地图元数据 | `C:\Users\LX\Desktop\保存的点位\0602-170853\ai_map.yaml` |

### 当前地图参数

```yaml
image: ai_map.pgm
mode: trinary
resolution: 0.05         # 每像素 0.05 米
origin: [-10, -10, 0]    # 左下角原点
negate: 0
occupied_thresh: 0.65
free_thresh: 0.25
```

### 地图文件替换（从本机 → 开发板）

```bash
# 将本机桌面上的地图文件覆盖到开发板上
scp C:/Users/LX/Desktop/保存的点位/0602-170853/ai_map.pgm davinci-mini@192.168.5.100:~/racecar/src/racecar/map/ai_map.pgm
scp C:/Users/LX/Desktop/保存的点位/0602-170853/ai_map.yaml davinci-mini@192.168.5.100:~/racecar/src/racecar/map/ai_map.yaml
```

### 地图文件下载（从开发板 → 本机）

```bash
# 使用 csv-manager 技能可自动按时间戳备份
# 或手动：
scp davinci-mini@192.168.5.100:~/racecar/src/racecar/map/ai_map.pgm /c/Users/LX/Desktop/
scp davinci-mini@192.168.5.100:~/racecar/src/racecar/map/ai_map.yaml /c/Users/LX/Desktop/
```

### 地图坐标与 CSV 航点的关系

CSV 中的航点坐标是 **map 坐标系下的世界坐标（米）**，与 PGM 地图像素通过 YAML 元数据关联：

```
world_x = origin_x + (col + 0.5) × resolution
world_y = origin_y + (height - 1 - row + 0.5) × resolution
```

---

## 10. Claude 技能速查表

| 技能 | 命令 | 用途 |
|------|------|------|
| 连接小车 | `/connect-davinci` | SSH 连接开发板并验证 |
| Git 管理 | `/racecar-git` | 扫描并提交 racecar 仓库 |
| CSV 管理 | `/csv-manager 下载` | 将航点下载到桌面（按时间戳建目录） |
| CSV 管理 | `/csv-manager 上传 <文件路径>` | 将本地 CSV 上传到开发板 |
| 摄像头管理 | `/camera-davinci` | 管理 USB 摄像头 |
| 录制视频 | `/record-video` | 录制并转 MP4 回传桌面 |
| 前视距离调参 | `/lookahead-tune` | 查询/修改 lookahead_dist |
| 自动导航 | `/auto-navigation` | 全自动多点导航 |
| 导航复盘 | 参阅 `导航复盘方案.md` | rosbag 录制 + Foxglove 分析 |

---

## 11. 调试命令速查

```bash
# 查看所有节点
ros2 node list

# 查看所有话题
ros2 topic list

# 查看话题频率
ros2 topic hz /scan
ros2 topic hz /odom_combined

# 查看话题数据
ros2 topic echo /odom_combined --once

# 查看 TF 树
ros2 run tf2_tools view_frames.py

# 可视化节点图
ros2 run rqt_graph rqt_graph

# 查看日志
ros2 run rqt_console rqt_console

# 查看参数
ros2 param list
ros2 param get /controller_server FollowPath.lookahead_dist

# 运行时修改参数
ros2 param set /controller_server FollowPath.lookahead_dist 0.7

# 可视化调参
ros2 run rqt_reconfigure rqt_reconfigure

# 录制话题数据（rosbag）
bash ~/racecar/src/racecar/scripts/record_nav.sh

# 紧急急停
ssh davinci-mini@192.168.5.100 "bash ~/racecar/src/racecar/scripts/emergency_stop.sh"
```

---

> 详细文档见知识库 `C:\Users\LX\Desktop\文档 - 机器人比赛\` 中的 12 份文档
