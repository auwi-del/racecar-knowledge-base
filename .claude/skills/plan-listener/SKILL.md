---
name: plan-listener
description: 在 davinci-mini 开发板上部署 /plan 话题监听器，实时打印路径分析并保存为明文 CSV
command: plan-listener
---

## 任务

在 davinci-mini 开发板上部署、运行和管理 `plan_listener.py` 脚本。该脚本订阅 `/plan`、`/goal_pose`、`/initialpose` 话题，每次收到 Nav2 规划的全局路径时自动保存为明文 CSV 文件并打印路径分析。

## 固定参数

| 参数 | 值 |
|------|-----|
| 开发板 IP | 192.168.5.100 |
| 用户名 | davinci-mini |
| SSH 方式 | 密钥认证（免密） |
| 目标路径 | `~/racecar/src/racecar/scripts/plan_listener.py` |
| 数据保存目录 | `~/racecar/path_records/` |
| CSV 格式 | `plan_<序号>_<时间戳>.csv`（明文，Excel 可直接打开） |

## 执行步骤

### 0. 前置检查

检查 SSH 连接：

```bash
ssh davinci-mini@192.168.5.100 "echo connected"
```

如果连接失败，先建立连接。

检查 `/plan` 话题是否存在（需已启动 nav.sh）：

```bash
ssh davinci-mini@192.168.5.100 "source /opt/ros/humble/setup.bash && ros2 topic list 2>/dev/null | grep /plan || echo 'NOT_FOUND'"
```

如果 `/plan` 话题不存在，说明 Nav2 未运行，需先启动 `bash ~/racecar/nav.sh`。

检查 Python 依赖：

```bash
ssh davinci-mini@192.168.5.100 "python3 -c \"import rclpy; from nav_msgs.msg import Path; from geometry_msgs.msg import PoseStamped; print('OK')\""
```

如果报错，安装缺失包：

```bash
ssh davinci-mini@192.168.5.100 "sudo apt install -y ros-humble-nav-msgs ros-humble-geometry-msgs 2>/dev/null; echo done"
```

### 1. 注入脚本（action=deploy）

将本地的 `plan_listener.py` 注入到开发板：

```bash
# 从本项目 skills/plan-listener/ 目录复制到开发板
scp .claude/skills/plan-listener/plan_listener.py davinci-mini@192.168.5.100:~/racecar/src/racecar/scripts/plan_listener.py
```

验证注入成功：

```bash
ssh davinci-mini@192.168.5.100 "ls -la ~/racecar/src/racecar/scripts/plan_listener.py && wc -l ~/racecar/src/racecar/scripts/plan_listener.py"
```

### 2. 运行监听器（action=run 或 deploy 后启动）

**方式 A：直接运行（快速）**

```bash
# 方法1：后台运行（适合常驻）
ssh davinci-mini@192.168.5.100 "source /opt/ros/humble/setup.bash && source ~/racecar/install/setup.bash && nohup python3 ~/racecar/src/racecar/scripts/plan_listener.py > /tmp/plan_listener.log 2>&1 & disown; echo 'started'"

# 方法2：前台运行（适合调试，需另开终端）
ssh davinci-mini@192.168.5.100 "source /opt/ros/humble/setup.bash && source ~/racecar/install/setup.bash && python3 ~/racecar/src/racecar/scripts/plan_listener.py"
```

**方式 B：注册为 ros2 run 命令（正式）**

```bash
# 修改 setup.py 添加入口
ssh davinci-mini@192.168.5.100 "grep -q plan_listener ~/racecar/src/racecar/setup.py || sed -i '/console_scripts/a\\        '\''plan_listener = racecar.scripts.plan_listener:main'\'',' ~/racecar/src/racecar/setup.py"

# 编译
ssh davinci-mini@192.168.5.100 "cd ~/racecar && colcon build --packages-select racecar 2>&1 | tail -3"

# 运行
ssh davinci-mini@192.168.5.100 "source ~/racecar/install/setup.bash && nohup ros2 run racecar plan_listener > /tmp/plan_listener.log 2>&1 & disown; echo 'started'"
```

### 3. 验证运行状态（action=status）

检查进程：

```bash
ssh davinci-mini@192.168.5.100 "ps aux | grep plan_listener | grep -v grep"
```

检查最近生成的 CSV：

```bash
ssh davinci-mini@192.168.5.100 "ls -lt ~/racecar/path_records/ 2>/dev/null | head -5 || echo 'NO_FILES'"
```

检查监听器日志：

```bash
ssh davinci-mini@192.168.5.100 "tail -20 /tmp/plan_listener.log 2>/dev/null || echo 'NO_LOG'"
```

### 4. 停止监听器（action=stop）

```bash
ssh davinci-mini@192.168.5.100 "pkill -f plan_listener.py 2>/dev/null; sleep 1; pgrep -f plan_listener || echo 'stopped'"
```

### 5. 下载路径 CSV 到本地（action=download）

```bash
# 打包所有路径 CSV
ssh davinci-mini@192.168.5.100 "cd ~/racecar && tar czf /tmp/path_records.tar.gz path_records/ 2>/dev/null && ls -lh /tmp/path_records.tar.gz"

# 下载到本机
scp davinci-mini@192.168.5.100:/tmp/path_records.tar.gz "./点位管理器/路径记录_$(date +%Y%m%d_%H%M%S).tar.gz"
```

报告下载位置给用户。

### 6. 向用户报告

```
═══════════════════════════════════════════
🗺️  plan_listener 状态
═══════════════════════════════════════════

  进程:  正在运行 ✅ / 未运行 ❌
  已保存: N 条路径 CSV
  保存到: ~/racecar/path_records/
  日志:   /tmp/plan_listener.log

  用法:
    分析路径:  /路径分析 <文件路径>
    下载数据:  /plan-listener download
    只运行:    /plan-listener run
    停止:      /plan-listener stop
═══════════════════════════════════════════
```

## 注意事项

- 监听器只订阅不发布，**不影响小车控制**
- 默认保存到 `~/racecar/path_records/`，目录不存在会自动创建
- 支持 `--no-save` 参数（仅打印不存文件）：`python3 ... --no-save`
- 支持 `--save-dir <路径>` 参数（自定义保存目录）
- 每收到一条 `/plan` 路径生成一个 CSV，去重机制保证相同路径不重复保存
- 单条 CSV 约 2~40KB，一场比赛 ~400KB，磁盘压力可忽略
- 赛后分析 CSV 可使用 `路径分析助手` skill
