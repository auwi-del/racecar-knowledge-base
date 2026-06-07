---
name: rosbag-recorder
description: 在 davinci-mini 开发板上部署和运行 rosbag 录制器，与 plan_listener 互补并存
command: rosbag-recorder
---

## 任务

在 davinci-mini 开发板上部署和运行 `rosbag_recorder.py` 脚本。该脚本通过调用 `ros2 bag record` 录制 ROS 话题为 rosbag 文件，与 `plan_listener.py`（录路径 CSV）互补。

**两者并存关系：**

```
同一目录下:
录制-0607_143022/
├── plan_0001_*.csv       ← plan_listener 生成（路径分析用，明文）
├── plan_0002_*.csv
├── ...
└── rosbag_20260607_143022/   ← rosbag_recorder 生成（原始数据，.db3）
    ├── rosbag_20260607_143022_0.db3
    └── metadata.yaml
```

## 固定参数

| 参数 | 值 |
|------|-----|
| 开发板 IP | 192.168.5.100 |
| 用户名 | davinci-mini |
| SSH 方式 | 密钥认证（免密） |
| 目标路径 | `~/racecar/src/racecar/scripts/rosbag_recorder.py` |
| 录制父目录 | `~/racecar/path_records/` |
| 默认话题 | `/plan /goal_pose /odom_combined /scan /car_cmd_vel /tf /tf_static` |

## 参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--dir` | `录制-MMDD_HHMMSS` | 自定义本次录制目录名 |
| `--topics` | 6个默认话题 | 录制的话题，逗号分隔 |
| `--all` | — | 录制所有话题 |
| `--duration` | 不限 | 最长录制时长（秒） |
| `--max-size` | 500MB | 单个 bag 文件最大体积 |
| `--compress` | — | 启用 zstd 压缩 |
| `--no-save` | — | 仅打印预览 |

## 执行步骤

### 0. 前置检查

```bash
ssh davinci-mini@192.168.5.100 "echo connected && source /opt/ros/humble/setup.bash && ros2 bag --help >/dev/null 2>&1 && echo 'ros2bag OK'"
```

### 1. 注入脚本（action=deploy）

```bash
scp .claude/skills/rosbag-recorder/rosbag_recorder.py davinci-mini@192.168.5.100:~/racecar/src/racecar/scripts/rosbag_recorder.py

# 添加到 CMakeLists.txt（如尚未添加）
ssh davinci-mini@192.168.5.100 "grep -q rosbag_recorder ~/racecar/src/racecar/CMakeLists.txt || sed -i '/^install(PROGRAMS/a\  scripts/rosbag_recorder.py' ~/racecar/src/racecar/CMakeLists.txt"

# 编译
ssh davinci-mini@192.168.5.100 "cd ~/racecar && source /opt/ros/humble/setup.bash && colcon build --packages-select racecar 2>&1 | tail -3"
```

### 2. 启动录制（action=run）

**默认录制（与 go.py 搭配）：**

```bash
ssh davinci-mini@192.168.5.100 "source ~/racecar/install/setup.bash && nohup ros2 run racecar rosbag_recorder.py > /tmp/rosbag_recorder.log 2>&1 & disown; echo 'started'"
```

**同时运行 plan_listener + rosbag_recorder（推荐组合）：**

```bash
# 终端2：路径 CSV 录制
ssh davinci-mini@192.168.5.100 "source ~/racecar/install/setup.bash && nohup ros2 run racecar plan_listener.py --dir 比赛第一轮 > /tmp/plan_listener.log 2>&1 & disown; echo 'plan_listener started'"

# 终端3：rosbag 录制
ssh davinci-mini@192.168.5.100 "source ~/racecar/install/setup.bash && nohup ros2 run racecar rosbag_recorder.py --dir 比赛第一轮 --compress --duration 300 > /tmp/rosbag_recorder.log 2>&1 & disown; echo 'rosbag started'"
```

> 注意：两个脚本用 **相同的 `--dir` 参数**，它们会自动存进同一个目录！

### 3. 验证状态（action=status）

```bash
ssh davinci-mini@192.168.5.100 "ps aux | grep rosbag_recorder | grep -v grep"
ssh davinci-mini@192.168.5.100 "ls -lt ~/racecar/path_records/ 2>/dev/null | head -5"
ssh davinci-mini@192.168.5.100 "tail -20 /tmp/rosbag_recorder.log 2>/dev/null || echo 'NO_LOG'"
```

### 4. 停止录制（action=stop）

```bash
ssh davinci-mini@192.168.5.100 "pkill -f rosbag_recorder.py 2>/dev/null; sleep 2; pgrep -f rosbag_recorder || echo 'stopped'"
```

### 5. 下载 rosbag 到本地（action=download）

```bash
# 打包录制数据（CSV + rosbag 一起打包）
ssh davinci-mini@192.168.5.100 "cd ~/racecar && tar czf /tmp/recordings.tar.gz path_records/ && ls -lh /tmp/recordings.tar.gz"

# 下载到本机
scp davinci-mini@192.168.5.100:/tmp/recordings.tar.gz "./点位管理器/录制数据_$(date +%Y%m%d_%H%M%S).tar.gz"
```

### 6. 向用户报告

```
═══════════════════════════════════════════
📦  rosbag_recorder 状态
═══════════════════════════════════════════

  进程:      正在录制 ✅ / 未运行 ❌
  本次录制:  录制-MMDD_HHMMSS/
  录制话题:  /plan /goal_pose /odom_combined ...
  格式:      rosbag (.db3)

  同时运行 plan_listener 的效果:
    同一个录制目录下既有 CSV（明文）又有 rosbag（原始）！

  用法:
    启动录制:        /rosbag-recorder run
    带时长限制:      /rosbag-recorder run (--duration 300)
    同时录路径:      /rosbag-recorder run (+ plan_listener 同时运行)
    下载数据:        /rosbag-recorder download
    停止:            /rosbag-recorder stop
═══════════════════════════════════════════
```

## 注意事项

- 本脚本通过 `subprocess` 调用 `ros2 bag record` CLI，**不直接使用 rclpy**，与 plan_listener 无 rclpy 冲突
- 与 plan_listener.py **可同时运行**，共用 `--dir` 参数时文件存到同一目录
- 默认录制 6 个话题（~20MB/分钟），加上 `--compress` 可减少 ~50% 体积
- `--all` 会录制所有话题（含 /image_raw 等），体积会大很多
- 回放 rosbag：`ros2 bag play <bag目录>`
- 查看 bag 信息：`ros2 bag info <bag目录>`
