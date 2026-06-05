---
name: csv-manager
description: 管理 davinci-mini 小车上的航点 CSV 文件和地图文件。支持下载到桌面备份（按时间戳建目录），或上传本地 CSV 替换板上的航点文件
command: csv
---

## 任务

管理 davinci-mini 小车上的航点文件和地图文件：

- **download**: 将开发板上的 `out_test.csv` + 地图 (PGM + YAML) 拷贝到 Windows 桌面 `保存的点位/时间戳/` 目录下
- **upload**: 将本机指定位置的 CSV 文件上传到开发板，替换 `out_test.csv`

## 固定参数

| 参数 | 值 |
|------|-----|
| 开发板 IP | 192.168.5.100 |
| 用户名 | davinci-mini |
| SSH 方式 | 密钥认证（免密） |
| 板上的航点文件 | `/home/davinci-mini/racecar/src/racecar/scripts/out_test.csv` |
| 板上的地图文件 | `/home/davinci-mini/racecar/src/racecar/map/ai_map.pgm` |
| 板上的地图元数据 | `/home/davinci-mini/racecar/src/racecar/map/ai_map.yaml` |
| 本地备份目录 | `C:\Users\LX\Desktop\保存的点位\` |

## 执行步骤

### 0. 前置检查

检查桌面备份目录是否存在，不存在则创建：

```bash
mkdir -p "/c/Users/LX/Desktop/保存的点位"
```

检查 SSH 连接：

```bash
ssh davinci-mini@192.168.5.100 "echo connected" 2>/dev/null
```

如果 SSH 连接失败，先提示用户建立连接。

### 1. 根据 action 参数分支处理

#### action = "download" — 从开发板下载到桌面

**1.1 检查板上源文件是否存在：**

```bash
ssh davinci-mini@192.168.5.100 "test -f /home/davinci-mini/racecar/src/racecar/scripts/out_test.csv && echo 'csv found' || echo 'csv not found'"
ssh davinci-mini@192.168.5.100 "test -f /home/davinci-mini/racecar/src/racecar/map/ai_map.pgm && echo 'map found' || echo 'map not found'"
```

如果 CSV 文件不存在，告知用户并退出。地图文件不存在则跳过地图下载。

**1.2 生成时间戳目录名：**

在本地获取当前时间，格式为 `MMDD-HHMMSS`，作为本次下载的子目录名。

创建目录：

```bash
mkdir -p "/c/Users/LX/Desktop/保存的点位/MMDD-HHMMSS"
```

**1.3 下载 CSV 文件：**

```bash
scp davinci-mini@192.168.5.100:/home/davinci-mini/racecar/src/racecar/scripts/out_test.csv "/c/Users/LX/Desktop/保存的点位/MMDD-HHMMSS/out_test.csv"
```

**1.4 下载地图文件（如存在）：**

如果地图 PGM 文件存在，下载 PGM 和 YAML，保持原始文件名：

```bash
scp davinci-mini@192.168.5.100:/home/davinci-mini/racecar/src/racecar/map/ai_map.pgm "/c/Users/LX/Desktop/保存的点位/MMDD-HHMMSS/ai_map.pgm"
scp davinci-mini@192.168.5.100:/home/davinci-mini/racecar/src/racecar/map/ai_map.yaml "/c/Users/LX/Desktop/保存的点位/MMDD-HHMMSS/ai_map.yaml"
```

**1.5 向用户报告：**

```
下载完成 ✅

  目录:  C:\Users\LX\Desktop\保存的点位\MMDD-HHMMSS\
  ├── out_test.csv    (N 个航点)
  ├── ai_map.pgm      (WxH 像素)
  └── ai_map.yaml     (分辨率 X m/像素)
```

#### action = "upload" — 从本机上传到开发板

**重要：上传必须无条件执行，无论本地文件看起来是否与板上文件一致。
用户可能修改了文件中的数值，禁止自作主张跳过上传。**

**2.1 检查本地文件是否存在：**

用户通过 `local_path` 参数指定本地 CSV 文件路径。如果未提供，提示用户输入。

```bash
test -f "/path/to/local/file.csv" && echo 'found' || echo 'not found'
```

如果文件不存在，报错并退出。

**2.2 检查文件格式（CSV 格式校验）：**

读取文件前几行，确认格式为 `x, y, z, w`（每行 4 个逗号分隔的浮点数）：

```bash
head -3 "/path/to/local/file.csv"
```

如果格式不匹配，警告用户但继续（非致命）。

**2.3 上传文件到开发板：**

```bash
scp "/path/to/local/file.csv" davinci-mini@192.168.5.100:/home/davinci-mini/racecar/src/racecar/scripts/out_test.csv
```

**2.4 验证上传成功：**

```bash
ssh davinci-mini@192.168.5.100 "head -3 /home/davinci-mini/racecar/src/racecar/scripts/out_test.csv && echo '---' && wc -l /home/davinci-mini/racecar/src/racecar/scripts/out_test.csv"
```

**2.5 向用户报告：**

```
上传完成 ✅

  来源:  /path/to/local/file.csv
  目标:  davinci-mini:~/racecar/src/racecar/scripts/out_test.csv
  航点数: N 个

  小车下次运行 `ros2 run racecar go` 时将使用新的航点文件。
```

## 注意事项

- 下载时目录 `桌面/保存的点位/` 会自动创建，每次下载都新建一个时间戳子目录
- 上传会**覆盖**板上的 `out_test.csv`，原文件不会被备份（如有需要先 download）
- 只校验 CSV 格式是否为 4 列浮点数，不校验坐标值是否在地图范围内
- 上传后小车正在运行的导航不受影响，下次启动 `go.py` 时使用新航点
