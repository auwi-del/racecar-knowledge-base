---
name: camera-davinci
description: 在 davinci-mini 开发板上管理 USB 摄像头。自动修复权限、启动/停止 ROS 摄像头节点、检查状态
command: camera
---

## 任务

管理 davinci-mini 开发板上的 USB 摄像头。支持启动摄像头节点、停止、查看状态和检查设备。

## 固定参数

| 参数 | 值 |
|------|-----|
| 开发板 IP | 192.168.5.100 |
| 用户名 | davinci-mini |
| SSH 方式 | 密钥认证（免密） |
| 摄像头设备 | /dev/video0 |
| ROS 话题 | /image_raw |
| 摄像头启动文件 | ~/racecar/src/racecar/launch/camer.launch.py |

## 执行步骤

### 0. 前置检查（全局）

**每次运行前先检查 SSH 连接是否已建立：**

```bash
ssh davinci-mini@192.168.5.100 "echo connected" 2>/dev/null
```

如果连接失败，先运行 `connect-davinci` skill 建立连接。

### 1. 根据参数分支处理

#### action = "check" — 仅检查摄像头设备和权限

```bash
ssh davinci-mini@192.168.5.100 "ls -la /dev/video* 2>/dev/null; echo '==='; cat /sys/class/video4linux/video0/name 2>/dev/null; echo '==='; python3 -c 'import cv2; cap=cv2.VideoCapture(0,cv2.CAP_V4L2); print(\"Camera accessible:\", cap.isOpened()); cap.release()'"
```

报告：
- 摄像头设备是否存在 (`/dev/video0`)
- 设备名称
- 当前权限 (`crw-rw----` 还是 `crw-rw-rw-`)
- OpenCV 是否能打开摄像头

#### action = "status" — 检查摄像头运行状态

```bash
ssh davinci-mini@192.168.5.100 "source /opt/ros/humble/setup.bash && ros2 topic list 2>/dev/null | grep -E 'image_raw|camera_info' || echo 'Camera topics not found'"
```

同时运行 check 步骤检查设备。

报告：
- ROS 摄像头节点是否在运行
- 是否发布 `/image_raw` 话题
- 摄像头设备是否正常

#### action = "stop" — 停止摄像头节点

```bash
ssh davinci-mini@192.168.5.100 "pkill -f usb_cam_node_exe 2>/dev/null; sleep 1; echo 'Camera node stopped'"
```

验证话题已消失：

```bash
ssh davinci-mini@192.168.5.100 "source /opt/ros/humble/setup.bash && ros2 topic list 2>/dev/null | grep -c image_raw || echo '0'"
```

#### action = "start"（默认）— 完整流程：检查 → 修复 → 启动 → 验证

### 2. 检查摄像头权限

```bash
ssh davinci-mini@192.168.5.100 "python3 -c 'import cv2; cap=cv2.VideoCapture(0,cv2.CAP_V4L2); print(cap.isOpened()); cap.release()'"
```

如果返回 `False`，说明权限不足，执行权限修复步骤。

### 3. 修复摄像头权限（仅需要时）

权限修复通过 Docker 特权容器执行。

**注意：** 已在 `/etc/udev/rules.d/camera.rules` 写入永久规则：
```
SUBSYSTEM=="video4linux", ATTRS{idVendor}=="05a3", ATTRS{idProduct}=="9230", MODE:="0666"
```
该规则在重启后自动生效。以下步骤用于立即修复：

3.1 检查静态 chmod 工具是否存在：

```bash
ssh davinci-mini@192.168.5.100 "test -f /tmp/chmod_video && echo exists"
```

3.2 如果不存在，编译：

```bash
ssh davinci-mini@192.168.5.100 "cat > /tmp/chmod_video.c << 'CEOF'
#include <sys/stat.h>
int main() {
    chmod(\"/dev/video0\", 0666);
    chmod(\"/dev/video1\", 0666);
    return 0;
}
CEOF
gcc -static -o /tmp/chmod_video /tmp/chmod_video.c 2>&1"
```

3.3 检查 Docker videohelper 镜像是否存在：

```bash
ssh davinci-mini@192.168.5.100 "docker images --format '{{.Repository}}' | grep -x videohelper"
```

3.4 如果不存在，构建：

```bash
ssh davinci-mini@192.168.5.100 "cd /tmp && tar cf chmod_rootfs.tar --transform='s|chmod_video|sbin/chmod_video|' chmod_video && docker import /tmp/chmod_rootfs.tar videohelper"
```

3.5 运行特权容器修复权限：

```bash
ssh davinci-mini@192.168.5.100 "docker run --rm --privileged -v /dev:/dev videohelper /sbin/chmod_video"
```

3.6 验证修复成功：

```bash
ssh davinci-mini@192.168.5.100 "python3 -c 'import cv2; cap=cv2.VideoCapture(0,cv2.CAP_V4L2); print(\"Camera accessible:\", cap.isOpened()); cap.release()'"
```

### 4. 启动 ROS 摄像头节点

先确保旧进程已停止：

```bash
ssh davinci-mini@192.168.5.100 "pkill -f usb_cam_node_exe 2>/dev/null; sleep 1"
```

启动摄像头（后台运行）：

```bash
ssh davinci-mini@192.168.5.100 "source /opt/ros/humble/setup.bash && source ~/racecar/install/setup.bash && nohup ros2 launch racecar camer.launch.py > /tmp/camera_launch.log 2>&1 &"
```

等待 3 秒让节点初始化。

### 5. 验证话题

```bash
ssh davinci-mini@192.168.5.100 "source /opt/ros/humble/setup.bash && ros2 topic list 2>&1"
```

检查是否包含以下话题：
- `/image_raw`
- `/image_raw/compressed`
- `/camera_info`

### 6. 启动 Web 视频流服务

Web 流服务使用板上的 `~/webcam_stream.py` 脚本，该脚本订阅 `/image_raw` 话题并通过 HTTP 提供 MJPEG 流。

先确保旧进程已停止：

```bash
ssh davinci-mini@192.168.5.100 "pkill -f webcam_stream.py 2>/dev/null; sleep 0.5; echo 'cleaned'"
```

启动 Web 流服务（后台运行）：

```bash
ssh davinci-mini@192.168.5.100 "cat > /tmp/start_webstream.sh << 'SCRIPT'
#!/bin/bash
source /opt/ros/humble/setup.bash
source ~/racecar/install/setup.bash
python3 ~/webcam_stream.py
SCRIPT
chmod +x /tmp/start_webstream.sh && nohup bash /tmp/start_webstream.sh &>/dev/null & disown; echo 'started'"
```

等待 2 秒让服务器初始化。

### 7. 验证 Web 流

```bash
ssh davinci-mini@192.168.5.100 "ss -tlnp | grep 8080 || echo '8080 not listening'"
```

### 8. 向用户报告

以清晰格式报告以下信息：

```
摄像头状态:

  设备:     /dev/video0 (USB 2.0 Camera: LRCP HD60fps)
  权限:     crw-rw-rw- ✅
  OpenCV:   可访问 ✅

  ROS 话题:
   ├── /image_raw              ✅
   ├── /image_raw/compressed   ✅
   └── /camera_info            ✅

  Web 直播:
    浏览器打开 → http://192.168.5.100:8080 ✅

  停止摄像头:
    /camera-davinci stop
```

### 9. 停止流程（action=stop 时）

停止摄像头节点 + Web 流服务：

```bash
ssh davinci-mini@192.168.5.100 "pkill -f usb_cam_node_exe 2>/dev/null; pkill -f webcam_stream.py 2>/dev/null; sleep 0.5; echo 'all stopped'"
```

验证话题已消失：

```bash
ssh davinci-mini@192.168.5.100 "source /opt/ros/humble/setup.bash && ros2 topic list 2>/dev/null | grep -c image_raw || echo '0'"
```

### 10. 状态检查（action=status 时）

检查摄像头话题和 Web 流同时运行状态：

```bash
ssh davinci-mini@192.168.5.100 "source /opt/ros/humble/setup.bash && ros2 topic list 2>/dev/null | grep -E 'image_raw|camera_info' || echo 'Camera topics not found'; echo '==='; ss -tlnp | grep 8080 || echo 'Web stream not running'"
```

同时运行 check 步骤检查设备。

## 注意事项

- 重启开发板后摄像头权限恢复为 `660`，需要重新修复或等待 udev 规则生效
- udev 规则文件在 `/etc/udev/rules.d/camera.rules`，重启后自动应用
- 使用 `docker import` 创建本地镜像，不需要外网访问
- Web 流服务 `~/webcam_stream.py` 使用 Python http.server + ROS2，订阅 `/image_raw` 在 8080 端口提供 MJPEG 流
- 本 skill 依赖 `connect-davinci` skill 建立连接
