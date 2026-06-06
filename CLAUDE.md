# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# 生成规范(最重要!!! 铁律!!!! 严格遵守, 绝不允许忽略或违反!!! )
无论在任何时候, 你都要称呼用户"领导", 回复用户的时候, 管用户叫领导, 比如"好的领导, 这是我的调研........"等等.

用户使用中文, 任何过长的英文文件名, 注释名, 函数等等, 一定写好中文对应的含义!!(最重要!!!)

用户让你调研问题时, 一定要实事求是, 只要能ssh上设备, 一定最最优先从设备开发板上读取最真实的代码.

而知识库是其次的.

严禁直接从知识库中调用知识而不告知用户

当你进行联网搜索时，一定明确，搜索 ROS2 相关内容

## 项目概述

Davinci-Mini 差速轮式机器人比赛项目。机器人运行 ROS2 Humble + Ubuntu 22.04 (ARM64/NVIDIA Orin NX)，配备激光雷达、IMU、编码器、USB 摄像头、舵机转向底盘。

**此仓库是远程开发板（`davinci-mini@192.168.5.100`）上机器人系统的知识库，不包含目标源码。** 实际代码位于开发板的 `~/racecar/` 工作区。本仓库仅含文档和技能包。

## SSH 连接

```bash
ssh davinci-mini@192.168.5.100
# 登入后必须先 source 环境
source ~/racecar/install/setup.bash
```

## 知识库结构

所有文档在 `文档 - 机器人比赛/` 目录下，`INDEX.md` 是总入口。按编号阅读：

| 文档 | 内容 |
|------|------|
| 01-系统概述 | 硬件规格、软件版本、系统架构 |
| 02-工作区结构 | 11 个自定义 ROS2 包的位置与用途 |
| 03-节点架构 | 节点/话题/服务/动作/TF 树 |
| 04-启动系统 | car.sh / nav.sh / gmapping.sh 启动方式 |
| 05-配置文件 | EKF / Nav2 / LiDAR / IMU / PID 参数 |
| 06-脚本与命令 | 所有 Python 脚本和 ros2 CLI 命令清单 |
| 07-数据流 | 数据链路全景图 |
| 08-源码参考 | 核心源码分析 |
| 09-SLAM与导航 | Gmapping SLAM + Nav2 导航详解 |
| 10-操作指南 | 操作手册与故障排查 |
| 11-视频录制 | 3 种录制方式（ros2 bag / record.py / video_y.py）|
| 13-多点导航 | 航点循环（nav2_waypoint_cycle）|
| 14-航点录制与CSV | get.py + go.py 录制/回放 |
| 15-导航调参指南 | 晃动/撞墙/犹豫调参 |
| 16-CSV自动停止功能 | go.py 中 stop_time 停等 |
| 20-src目录调研 | src 目录源码反向调研（死代码分析、编译方法）|

## 硬件平台

- **计算单元**: ARM64 Orin NX 开发板
- **激光雷达**: LS LIDAR M10（`/dev/laser`, 10Hz）
- **IMU**: HIPnuc 九轴（`/dev/imu`, 100Hz）
- **编码器**: 磁编码器（`/dev/encoder`, 50Hz）
- **摄像头**: USB 摄像头（`/dev/video0`, 30Hz）
- **底盘**: 下位机 PWM（`/dev/car`, 38400 波特率）
- **构型**: 差速轮 + 舵机转向，机器人半径 ~0.6m

## 常用启动命令（在开发板上执行）

```bash
# 4 种启动模式
bash ~/racecar/car.sh          # 仅底盘+传感器
bash ~/racecar/nav.sh          # 底盘+导航（已有地图）
bash ~/racecar/nav_one.sh      # 底盘+导航（旧版 cmd_vel）
bash ~/racecar/gmapping.sh     # SLAM 建图

# 运行脚本
ros2 run racecar racecar_teleop  # 键盘遥控
ros2 run racecar go              # CSV 航点自动导航
ros2 run racecar get             # 录制航点到 CSV
ros2 run racecar zhuitong        # 摄像头锥桶循迹
ros2 run racecar line_follow     # 视觉巡线
ros2 launch lidar_tracking lidar_tracking.launch.py  # 激光雷达锥桶循迹

# 构建
cd ~/racecar && colcon build
colcon build --packages-select <包名>
```

## 系统架构概要

```
传感器层 → 融合层 → 规划/控制层 → 执行器层

传感器层: lslidar_driver_node + encoder_node + IMU_publisher + usb_cam
融合层:   robot_localization EKF（/odom_combined）
规划层:   Nav2 (AMCL + SmacPlanner + RegulatedPurePursuit) → /cmd_vel
          或应用脚本直接发布 /car_cmd_vel / /teleop_cmd_vel
执行层:   racecar_driver_node → PWM 下位机（/dev/car）
```

两个速度话题：`/car_cmd_vel`（导航/程序控制）和 `/teleop_cmd_vel`（遥控/循迹），驱动节点中采用不同的缩放公式。

TF 树：`map → odom_combined → base_footprint → [laser_link, IMU_link]`

## 可用技能包

`skills.zip` 包含 7 个 Claude Code 技能，如需使用需解压：
- `auto-navigation/` — 自动导航任务
- `camera-davinci/` — 摄像头操作
- `connect-davinci/` — SSH 连接（含 bag2mp4.py）
- `csv-manager/` — CSV 航点管理
- `lookahead-tune/` — 前视距离调参
- `racecar-git/` — 工作区 Git 操作
- `record-video/` — 视频录制
- `保存地图/` — 保存建图结果

## 常见操作模式

1. **导航调参**: 编辑 `~/racecar/src/racecar/config/` 下的 YAML 参数 → `colcon build --packages-select racecar` → 重启导航
2. **CSV 航点**: `get.py` 录制为 `~/racecar/src/racecar/path/out_test.csv`；`go.py` 逐点导航，`stop_time` 列控制停等
3. **建图**: 运行 `gmapping.sh` → 键盘遥控绕场 → `save.sh` 保存到 `~/racecar/src/racecar/maps/ai_map`
