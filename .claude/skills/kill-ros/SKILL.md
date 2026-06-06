---
name: kill-ros
description: SSH 到开发板，一键杀掉所有 ROS 相关进程
disable-model-invocation: true
---

## 任务

SSH 到 davinci-mini 开发板，列出所有 ROS 相关进程并直接杀掉。

## 固定参数

| 参数 | 值 |
|------|-----|
| 开发板 IP | 192.168.5.100 |
| 用户名 | davinci-mini |
| SSH 方式 | 密钥认证（免密）✅ |
| 工作区路径 | `~/racecar` |

## 执行步骤

### 1. SSH 连通性检查

```bash
ssh davinci-mini@192.168.5.100 "echo connected" 2>/dev/null
```

如果连接失败，先运行 `connect-davinci` skill。

### 2. 查找 ROS 相关进程

搜索以下关键词：`ros2` `lslidar` `racecar_driver` `encoder` `component_container` `python3` `rviz` `ekf` `static_transform` `joint_state` `talker` `listener` `waypoint` `nav2` `amcl` `planner` `controller` `bt_navigator` `behavior_server` `velocity_smoother` `smoother_server` `map_server` `lifecycle_manager` `laser`

```bash
ssh davinci-mini@192.168.5.100 "ps aux | grep -E 'ros2|lslidar|racecar_driver|encoder|component_container|python3|rviz|ekf|static_transform|joint_state|talker|listener|waypoint|nav2|amcl|planner|controller|bt_navigator|behavior_server|velocity_smoother|smoother_server|map_server|lifecycle_manager|laser' | grep -v grep"
```

### 3. 显示进程信息

将上一步的结果逐行列在屏幕上，显示:
- PID
- CPU%  MEM%
- 启动时间
- 命令行（完整命令）

### 4. 强制杀掉进程

```bash
ssh davinci-mini@192.168.5.100 "killall -9 lslidar_driver_node racecar_driver_node encoder_node static_transform_publisher joint_state_publisher talker listener ekf_node component_container_isolated component_container_mt rviz2 ros2 python3 nav2_waypoint_cycle 2>/dev/null; echo '所有ROS进程已清理'"
```

### 5. 验证清理

```bash
ssh davinci-mini@192.168.5.100 "ps aux | grep -E 'ros2|lslidar|racecar_driver|encoder|component_container|rviz|ekf|nav2|amcl' | grep -v grep | wc -l"
```

如果还有残留进程，列出 PID 并用 `kill -9` 逐个杀掉。

### 6. 向用户报告

```
ROS 进程清理完毕

已杀进程:
  - lslidar_driver_node     (PID: XXXX)
  - racecar_driver_node      (PID: XXXX)
  - encoder_node            (PID: XXXX)
  - component_container     (PID: XXXX)
  - 其他 N 个进程 ...

验证: 剩余 ROS 进程数: 0 ✅
提示: 运行 bash ~/racecar/nav.sh 重新启动
```

## 参数说明

无参数，直接执行完整清理流程。
