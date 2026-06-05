---
name: save-map
description: 将 davinci-mini ROS 开发板上的最新地图保存到本机 Windows 桌面
disable-model-invocation: true
---

## 任务

将 davinci-mini 开发板上的最新地图保存并复制到本机 Windows 桌面。

## 固定参数

| 参数 | 值 |
|------|-----|
| 开发板 IP | 192.168.5.100 |
| 用户名 | davinci-mini |
| SSH 方式 | 密钥认证（免密） |
| 地图目录 | ~/racecar/src/racecar/map |
| 地图名称 | ai_map |

## 执行步骤

### 1. 在开发板上保存地图

通过 SSH 执行地图保存命令：

```bash
ssh davinci-mini@192.168.5.100 "cd ~/racecar && bash save.sh"
```

检查保存是否成功：

```bash
ssh davinci-mini@192.168.5.100 "ls -la ~/racecar/src/racecar/map/ai_map.*"
```

### 2. 复制地图文件到 Windows 桌面

```bash
scp davinci-mini@192.168.5.100:/home/davinci-mini/racecar/src/racecar/map/ai_map.* /c/Users/LX/Desktop/
```

### 3. 验证结果

检查桌面文件：

```bash
ls -la /c/Users/LX/Desktop/ai_map.*
```

### 4. 向用户报告

- 显示保存的地图文件信息（pgm 大小、yaml 内容摘要）
- 告知文件已保存到桌面路径
