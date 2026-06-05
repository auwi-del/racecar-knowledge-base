---
name: auto-navigation
description: 从零开始全自动化启动 davinci-mini 多点导航。自动 SSH 连接、检查地图、启动导航栈、发布航点、监控执行状态
command: navigate
---

## 任务

从 **零状态**（未建立 SSH 连接）到启动完整的多点导航系统全自动化。传入可选的 `waypoints` 参数指定航点，未传入则询问用户。

## 固定参数

| 参数 | 值 |
|------|-----|
| 开发板 IP | 192.168.5.100 |
| 用户名 | davinci-mini |
| SSH 方式 | 密钥认证（免密） |
| 导航启动脚本 | `~/racecar/nav.sh` |
| 地图路径 | `~/racecar/src/racecar/map/ai_map.yaml` |

## 执行步骤

### 第1步：检查 SSH 连接

```bash
ssh davinci-mini@192.168.5.100 "echo connected" 2>/dev/null
```

如果连接失败，检查网络连通性：

```bash
ping -n 2 -w 1000 192.168.5.100
```

- 如果 ping 不通，告知用户检查网线连接和本机 IP 是否在 `192.168.5.x` 网段
- 如果 ping 通但 SSH 连不上，检查 SSH 密钥和开发板状态

### 第2步：检查前置条件

检查 nav.sh 是否存在：

```bash
ssh davinci-mini@192.168.5.100 "test -f ~/racecar/nav.sh && echo 'nav.sh OK' || echo 'nav.sh MISSING'"
```

检查地图文件是否存在：

```bash
ssh davinci-mini@192.168.5.100 "test -f ~/racecar/src/racecar/map/ai_map.yaml && echo 'map OK' || echo 'map MISSING'"
```

如果地图不存在，提示用户先建图并中止流程。

### 第3步：检查是否已有导航系统在运行

```bash
ssh davinci-mini@192.168.5.100 "source /opt/ros/humble/setup.bash && ros2 node list 2>/dev/null | grep -c 'amcl\|bt_navigator\|waypoint_cycle'" || echo "0"
```

如果已有节点运行（计数 >= 3），跳过启动步骤，直接跳到第6步发布航点。

否则继续。

### 第4步：安全清理旧进程

**注意**：不要用 `pkill -f 'nav.sh'`，这会把 SSH 命令行自身也杀掉。使用更精确的方式：

```bash
ssh davinci-mini@192.168.5.100 "ps aux | grep -E 'ros2.*launch|nav\.sh' | grep -v grep | awk '{print \$2}' | xargs kill -9 2>/dev/null; sleep 2; echo 'cleaned'"
```

### 第5步：启动导航系统

**DISPLAY 处理**：nav.sh 会启动 rviz2，但 SSH 没有 DISPLAY。需要先设置虚拟显示，或者直接忽略启动 rviz2 失败（不影响导航功能）。

先检查 DISPLAY，如果未设置则尝试设置：

```bash
ssh davinci-mini@192.168.5.100 "echo DISPLAY=\${DISPLAY:-unset}"
```

如果没有 DISPLAY，使用 `xvfb-run` 或设置 `DISPLAY=:0`：

```bash
ssh davinci-mini@192.168.5.100 "cd ~/racecar && DISPLAY=:0 nohup bash nav.sh &>/tmp/nav.log & disown && echo 'nav started'"
```

如果上述命令失败（rviz2 报错但不影响导航功能），也可以直接启动 launch 组件而非 nav.sh 脚本：

```bash
ssh davinci-mini@192.168.5.100 "cd ~/racecar && source /opt/ros/humble/setup.bash && source install/setup.bash && nohup ros2 launch racecar Run_car.launch.py &>/tmp/nav_car.log & nohup ros2 launch racecar Run_nav.launch.py &>/tmp/nav_nav.log & disown && echo 'launch started'"
```

#### 等待系统初始化

等待 20 秒让传感器、EKF、AMCL、Nav2 等完成初始化。

#### 验证节点启动

```bash
ssh davinci-mini@192.168.5.100 "source /opt/ros/humble/setup.bash && ros2 node list 2>/dev/null"
```

检查以下关键节点是否全部在线：
- `amcl` — 定位
- `bt_navigator` — 行为树导航
- `controller_server` — 控制器
- `planner_server` — 规划器
- `waypoint_cycle` — 航点循环

如果节点数 < 3，说明启动异常，检查日志：

```bash
ssh davinci-mini@192.168.5.100 "tail -30 /tmp/nav.log 2>/dev/null || tail -30 /tmp/nav_car.log"
```

### 第6步：获取航点

通过 AskUserQuestion 工具向用户询问航点。展示以下选项：

```
请提供导航航点（地图坐标系下的 x y 坐标）：

方式1: 直接输入一系列坐标，每行一个 "x y"
方式2: 使用默认示例航点
```

如果用户选择使用默认航点或传入了 `waypoints` 参数，使用预设值：

```
默认航点示例：
  (0.0, 0.0) — 起点（地图原点）
  (1.0, 0.0) — 向右 1 米
  (1.0, 1.0) — 右前方
  (0.0, 1.0) — 前方
```

### 第7步：发布航点

按顺序逐个发布航点到 `/clicked_point` 话题，每个间隔 2 秒：

```bash
ssh davinci-mini@192.168.5.100 "source /opt/ros/humble/setup.bash && ros2 topic pub /clicked_point geometry_msgs/msg/PointStamped '{header: {frame_id: \"map\"}, point: {x: X_VAL, y: Y_VAL}}' --once 2>/dev/null"
```

每发布一个航点，向用户报告进度（`航点 N/M 已设置 → (x, y)`）。

第1个航点发布后，`waypoint_cycle` 会自动触发导航，小车开始移动。

### 第8步：监控导航状态

发布完所有航点后，监控导航状态。每 5-10 秒检查一次：

```bash
ssh davinci-mini@192.168.5.100 "source /opt/ros/humble/setup.bash && timeout 5 ros2 topic echo /navigate_to_pose/_action/status --once 2>/dev/null"
```

持续监控并向用户报告：

```
🚗 正在前往航点 1/4 (目标: x=1.0, y=0.0)...
✅ 到达航点 1/4 — waypoint_cycle 自动发下一个
🚗 正在前往航点 2/4 (目标: x=1.0, y=1.0)...
...
🔄 全部航点完成！waypoint_cycle 自动从头循环
```

如果某个航点连续 2 次失败，waypoint_cycle 会自动跳过，继续下一个。

### 第9步：向用户报告

最终报告格式：

```
多点导航已启动 ✅

系统状态:
  SSH连接:     ✅
  地图:        ai_map
  导航节点:    AMCL ✅ 规划器 ✅ 控制器 ✅ BT导航 ✅
  航点数量:    N 个

航点列表:
  1 → (x1, y1)
  2 → (x2, y2)
  ...

当前状态: 🚗 正在前往航点 1/N
waypoint_cycle 将在全部完成后自动循环。

提示:
  - 实时画面: http://192.168.5.100:8080/stream（需先启动摄像头）
  - 同时录制: /record 200
  - 干预控制: 另开终端运行 ros2 run racecar racecar_teleop
```

### 第10步：持续监控（可选）

询问用户是否需要继续监控（每 10 秒汇报一次），还是退出监控让小车自主运行。

如果用户选择退出监控，告知他们可以使用以下命令随时查看状态：

```bash
ssh davinci-mini@192.168.5.100 "source /opt/ros/humble/setup.bash && ros2 topic echo /navigate_to_pose/_action/status --once 2>/dev/null"
```

## 注意事项

- ⚠️ `pkill -f 'nav.sh'` 会误杀自身的 SSH 进程，需要用更精确的进程匹配方式
- DISPLAY 未设置不影响导航功能（仅 rviz2 不可用）
- 第1个航点发布后 waypoint_cycle 会立即触发导航
- 全部航点到达后自动从头循环（无止境）
- 导航过程中可以随时另开终端进行其他操作
