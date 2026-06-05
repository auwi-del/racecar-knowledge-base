# RViz 地图与代价网格加载慢的原因分析与解决方案

## 现象

运行 `bash ~/racecar/nav.sh` 后：

1. RViz 窗口弹出很快（几秒内）
2. 但地图（灰色/黑色栅格）显示出来需要较长时间
3. 紫色代价网格（global_costmap / local_costmap 的 inflation 层）加载更慢，逐片出现

## 原因分析

### 原因一：SSH X11 转发是首要瓶颈 🔴 最严重

本机通过 `ssh -X` / `ssh -Y` 将开发板的 RViz 窗口转发到本地显示。问题的核心在于：

| 对比项 | 本地运行 | SSH X11 转发 |
|--------|---------|-------------|
| 渲染方式 | GPU 硬件加速（OpenGL） | 回退到 **Mesa 软件渲染** |
| 地图更新 | 本地纹理上传到 GPU，毫秒级 | 每个像素需序列化通过 SSH 隧道传输 |
| 代价网格 | GPU 绘制覆盖层，一次完成 | CPU 逐帧软件渲染再传输 |
| 帧缓存 | 直接写显存 | 需编码 → 网络传输 → 本机解码 |

具体影响：

- `/map` 话题在 ROS 层面传输很快（地图文件通常仅几百 KB）
- **但 RViz 渲染后的每一帧**，都必须通过 SSH 把 OpenGL 绘制命令和像素数据传回你的电脑
- X11 协议对 OpenGL 加速的支持极差（`GLX` 协议在 SSH 隧道中几乎不可用），会自动回退到软件渲染
- 代价网格（紫色层）由 **3 个图层叠加**（static_layer + obstacle_layer + inflation_layer），渲染数据量是纯地图的数倍

**结论**：这是加载慢的第一大原因，所有图形数据都需要过一遍网络 + 软件渲染。

### 原因二：启动序列中有 10 秒硬等待 🟡 设计使然

`nav.sh` 的启动时间线：

```
t=0s    car.sh → Run_car.launch.py → 传感器 + 底盘 + RViz 先启动
t=10s   sleep 10                    ← 硬等 10 秒
t=10s+  Run_nav.launch.py → AMCL + map_server + planner + costmaps
```

- 前 10 秒 RViz 窗口已弹出，但地图/导航尚未启动，画面空白
- 等到 t=10s+ 才开始依次加载地图、初始化 AMCL、构建代价地图
- 这 10 秒的"空白期"会让人感觉加载慢

### 原因三：代价地图多层构建需要时间 🟡 正常启动流程

Nav2 启动后，紫色网格（global_costmap）的构建分 4 步：

```
map_server 加载 ai_map.pgm（约 92KB 左右）
    ↓ 发布 /map 话题
static_layer 订阅 /map → 转换为底层代价地图
    ↓ 等待激光雷达 /scan 话题数据
obstacle_layer 接收激光帧 → 注入动态障碍物
    ↓ 数学计算
inflation_layer 在障碍物周围膨胀 → 生成紫色渐变区域
    ↓ 发布 /global_costmap/costmap
RViz 接收并进行渲染 ← X11 转发到这里再卡一次
```

每个图层都有初始化时间，激光雷达首帧数据通常在启动后几百毫秒~1 秒才到达（雷达 10Hz）。再加上 X11 转发渲染的叠加，总体感觉就是"地图慢慢亮起来，紫色一片片出现"。

### 原因四（潜在）：地图分辨率精细

当前地图参数（来自 `config/nav.yaml` 引用的 `maps/ai_map.yaml`）：

```yaml
image: ai_map.pgm
resolution: 0.05          # 每像素 0.05m（5cm），精细
origin: [-22.8, -10, 0]   # 跨度 ~23m × 10m
```

- `0.05m/px` 精度较高，对于比赛场地来说是足够的，但绘图数据量是 `0.10m/px` 方案的 4 倍
- 代价地图以同样分辨率构建，多层叠加后数据量进一步放大

---

## 验证方法

### 判断是否为 X11 瓶颈

通过检查 CPU 负载来判断：

```bash
ssh davinci-mini@192.168.5.100
top   # 在启动 nav.sh 后观察 rviz2 的 CPU 使用率
```

- 如果 `rviz2` 进程 CPU 占用 > 50% → 说明是 **软件渲染** 导致的卡顿
- 如果 `rviz2` CPU 低但就是显示慢 → 可能是 **网络带宽** 瓶颈

### 检查地图数据是否正常到达

用另一个终端（或提前开好）：

```bash
ssh davinci-mini@192.168.5.100
# 查看 /map 话题的频率和大小
ros2 topic hz /map
ros2 topic bw /map
# 查看代价地图话题
ros2 topic hz /global_costmap/costmap
```

如果话题频率正常但显示慢 → 基本确定是 X11 渲染/传输问题。

---

## 解决方案

### 方案 1：SSH 启用压缩（最简单，先试）

```bash
ssh -Y -C davinci-mini@192.168.5.100
# 然后正常启动
bash ~/racecar/nav.sh
```

`-C` 开启 SSH 压缩，地图这种大面积重复像素的数据压缩率较高，能显著减少 X11 数据的传输量。

### 方案 2：缩短 nav.sh 的 sleep 时间

```bash
# 编辑 nav.sh，找到 sleep 10
# 改为
sleep 3
# 或改为等待 /scan 话题有数据再启动（较复杂，需要修改脚本逻辑）
```

### 方案 3：使用 VNC 替代 X11 转发（推荐长期方案）

X11 转发对 OpenGL 应用不友好，VNC 的帧缓冲机制更高效。

**在开发板上安装 VNC 服务端：**

```bash
sudo apt update
sudo apt install tigervnc-standalone-server
```

**启动 VNC 服务：**

```bash
# 首次启动需要设置密码
vncserver -localhost no :1
# -localhost no 允许远程连接（仅限安全网络）
```

**在本机连接：**
- Windows：用 VNC Viewer（RealVNC / TightVNC）
- 地址：`192.168.5.100:1`

**优点：**
- VNC 传输的是压缩后的帧缓冲，比 X11+OpenGL 高效得多
- 无需安装额外软件在开发板上（tigervnc 很轻量）

### 方案 4：后续建图时降低分辨率

如果将来重建地图，可以在 `gmapping.sh` 的 launch 文件中调整参数，将地图分辨率从 `0.05` 改为 `0.10`：

- 地图文件缩小 4 倍
- 代价地图构建速度提升
- X11 传输量大减
- 对比赛导航精度影响较小

### 方案 5：禁用 RViz 中不必要的显示

在 RViz 中关闭不需要的显示插件：
- 如果不需要实时看到 costmap，取消勾选 `Map → Global Costmap` / `Local Costmap`
- 减少显示的 TF 树层级
- 降低 LaserScan 的显示点数

---

## 总结优先级

| 优先级 | 方案 | 难度 | 预期效果 |
|--------|------|------|---------|
| ⭐1 | `ssh -Y -C` 压缩连接 | 极低 | 中等改善 |
| ⭐2 | `sleep 10` → `sleep 3` | 低 | 减少等待感 |
| ⭐3 | 改用 VNC | 中 | 大幅改善 |
| ⭐4 | 后续建图降低分辨率 | 低（下次建图时） | 根本改善 |
| ⭐5 | 简化 RViz 显示内容 | 低 | 小幅改善 |
