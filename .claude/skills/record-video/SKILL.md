---
name: record-video
description: 在 davinci-mini 开发板上录制摄像头视频，自动转 MP4 并拷贝到 Windows 桌面
command: record
---

## 任务

在 davinci-mini 开发板上录制 USB 摄像头画面，自动转换为 MP4，并复制到本机 Windows 桌面。

## 固定参数

| 参数 | 值 |
|------|-----|
| 开发板 IP | 192.168.5.100 |
| 用户名 | davinci-mini |
| SSH 方式 | 密钥认证（免密） |
| 摄像头话题 | /image_raw |
| 桌面路径 | C:\Users\LX\Desktop |
| 转换脚本 | ~/bag2mp4.py |

## 执行步骤

### 0. 参数校验

用户传入的 `duration` 参数必须为整数，范围 **10~500**（秒）。

如果超出范围，直接报错并终止。

### 1. 前置检查：SSH 连接

```bash
ssh davinci-mini@192.168.5.100 "echo connected" 2>/dev/null
```

如果连接失败，先运行 `connect-davinci` skill 建立连接。

### 2. 检查摄像头节点

```bash
ssh davinci-mini@192.168.5.100 "source /opt/ros/humble/setup.bash && ros2 topic list 2>/dev/null | grep /image_raw"
```

如果 `/image_raw` 不在列表中，先运行 `camera-davinci start` skill 启动摄像头。

### 3. 录制视频

在开发板上执行录制，时长由 `duration` 参数决定：

```bash
ssh davinci-mini@192.168.5.100 "source /opt/ros/humble/setup.bash && timeout ${duration} ros2 bag record -o ~/bag_record /image_raw 2>&1"
```

生成的文件在 `~/bag_record/` 目录下。

### 4. 转换为 MP4

```bash
ssh davinci-mini@192.168.5.100 "source /opt/ros/humble/setup.bash && python3 ~/bag2mp4.py ~/bag_record ~/bag_record_video.mp4 2>&1"
```

### 5. 复制到 Windows 桌面

使用 `scp` 将 MP4 文件拷贝到本机桌面：

```bash
scp davinci-mini@192.168.5.100:~/bag_record_video.mp4 "/c/Users/LX/Desktop/录制视频_$(date +%Y%m%d_%H%M%S).mp4"
```

### 6. 清理开发板临时文件

```bash
ssh davinci-mini@192.168.5.100 "rm -rf ~/bag_record ~/bag_record_video.mp4"
```

### 7. 向用户报告

输出示例：

```
录制完成 ✅

  时长:    10 秒
  分辨率:  320×240
  帧数:    277 帧
  文件:    C:\Users\LX\Desktop\录制视频_20260530_180000.mp4
  大小:    1.1 MB
```

## 注意事项

- 本 skill 依赖 `connect-davinci` skill 建立 SSH 连接
- 本 skill 依赖 `camera-davinci` skill 启动摄像头（如果尚未运行）
- 录制时长最长 500 秒（约 8 分钟），最短 10 秒
- 转换脚本 `~/bag2mp4.py` 需预先部署在开发板上
