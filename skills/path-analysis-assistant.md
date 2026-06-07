---
name: path-analysis-assistant
description: Read plan_listener.py CSV path files, analyze path quality (smoothness/safety/efficiency/curvature), diagnose navigation issues, suggest nav.yaml tuning parameters
---

# 🗺️ Path Analysis Assistant — Skill

> **适用场景**：通过 `plan_listener.py` 录制了 `/plan` 路径 CSV 后，让 AI 读取并分析路径质量、诊断导航问题。

---

## 一、CSV 文件格式说明

### 1.1 文件来源

由 `plan_listener.py` 在每次收到 Nav2 规划的全局路径时自动生成，保存到 `~/racecar/path_records/` 目录。

### 1.2 文件命名

```
plan_<序号4位>_<时间戳>.csv
示例：plan_0003_20260607_143022.csv
```

- 序号：从 `0001` 开始递增，每收到一条新路径 +1
- 时间戳：文件生成时间，格式 `YYYYMMDD_HHMMSS`

### 1.3 文件内部结构

```
# plan_listener 路径记录
# 生成时间: 2026-06-07 14:30:22
# 帧: map | 路径点数: 287 | 总长: 15.83m
# 起点: (1.9600, -0.2900) | 终点: (3.1268, -0.5585)
# 起点朝向: 175.3° | 终点朝向: 191.2°
# 曲折比: 13.53x | 弯曲度: 中等（含缓弯）
# 目标点: (3.1268, -0.5585) 朝向 176.2° (来自 /goal_pose 第2次)
#
# point_id, x, y, yaw_deg, segment_dist
0, 1.960000, -0.290000, 175.30, 0.000000
1, 2.049500, -0.254300, 176.20, 0.095431
2, 2.142800, -0.318700, 177.10, 0.106732
...
286, 3.120000, -0.550000, 190.80, 0.015234
```

### 1.4 各列定义

| 列名 | 单位 | 说明 |
|:----:|:----:|:------|
| `point_id` | — | 路径点序号，从 0 开始 |
| `x` | 米 | 地图坐标系 X 坐标 |
| `y` | 米 | 地图坐标系 Y 坐标 |
| `yaw_deg` | 度 | 该点的朝向角（0~360°，正东为 0°，逆时针增加） |
| `segment_dist` | 米 | 该点到上一个点的间距（第 0 行为 0） |

### 1.5 元数据头（以 `#` 开头的行）

| 元数据字段 | 含义 | 典型值 |
|-----------|------|--------|
| `帧` | 路径所在的坐标系 | `map` |
| `路径点数` | 路径包含的坐标点数量 | `287` |
| `总长` | 所有 segment_dist 之和 | `15.83m` |
| `起点` | 第 0 个路径点的 (x, y) | `(1.96, -0.29)` |
| `终点` | 最后 1 个路径点的 (x, y) | `(3.13, -0.56)` |
| `起点朝向` | 出发时的朝向角 | `175.3°` |
| `终点朝向` | 到达时的朝向角 | `191.2°` |
| `曲折比` | 路径总长 ÷ 起点到终点直线距离 | `13.53x` |
| `弯曲度` | AI 自动评估的弯道程度 | `中等（含缓弯）` |
| `目标点` | 本次导航的目标（来自 /goal_pose） | `(3.13, -0.56) 朝向 176.2°` |

---

## 二、路径质量分析框架

### 2.1 四个分析维度

```
┌─────────────────────────────────────────────────┐
│              路径质量分析框架                        │
├──────────┬──────────┬──────────┬──────────────────┤
│  平滑度   │  安全性   │  效率    │  曲率合理性        │
│          │          │          │                  │
│ 路径是否  │ 路径是否  │ 路径是否  │ 转弯是否符合       │
│ 顺滑流畅  │ 居中走，  │ 绕路，    │ 车辆最小转弯       │
│ 无锯齿   │ 不贴墙   │ 曲折比   │ 半径约束          │
└──────────┴──────────┴──────────┴──────────────────┘
```

### 2.2 具体指标

| 指标 | 计算方法 | 良好 | 警告 | 异常 |
|:----:|---------|:----:|:----:|:----:|
| **曲折比** | 路径总长 ÷ 直线距离 | < 1.2x | 1.2x ~ 1.5x | > 1.5x |
| **段间距一致性** | segment_dist 的标准差 ÷ 均值 | < 0.3 | 0.3 ~ 0.5 | > 0.5 |
| **角度突变** | 相邻点的 yaw_deg 差值绝对值 | < 5° | 5° ~ 15° | > 15° |
| **路径点数** | 总点数 | > 20 | 5 ~ 20 | < 5 |
| **转弯半径** | segment_dist ÷ abs(角度变化_弧度) | > 0.6m | 0.3 ~ 0.6m | < 0.3m |

### 2.3 典型问题诊断

#### 问题 1：路径左右锯齿（晃动）

**CSV 表现**：
- yaw_deg 频繁正负交替（如 175° → 178° → 174° → 179°）
- segment_dist 忽大忽小
- 路径在 x-y 散点图上呈 S 形

**根因**：
```
lookahead_dist（前视距离）太小，小于 minimum_turning_radius（最小转弯半径）
当前：lookahead_dist=0.3m, minimum_turning_radius=0.6m
建议：lookahead_dist ≥ minimum_turning_radius
```

**推荐调整**：
```yaml
# nav.yaml controller_server.FollowPath
lookahead_dist: 0.3 → 0.7
min_lookahead_dist: 0.3 → 0.5
max_lookahead_dist: 0.6 → 1.0
```

#### 问题 2：路径贴墙走（撞墙风险）

**CSV 表现**：
- 路径点明显偏向地图边界
- 与障碍物的间距（需配合地图）偏小

**根因**：
```
inflation_radius（膨胀半径）太小，路径规划时安全余量不足
当前：全局 0.15m, 局部 0.25m
建议：全局 0.4m, 局部 0.5m（车半径 0.6m）
```

**推荐调整**：
```yaml
# nav.yaml costmap
global_costmap.inflation_layer.inflation_radius: 0.15 → 0.4
local_costmap.inflation_layer.inflation_radius: 0.25 → 0.5
```

#### 问题 3：路径大绕路（效率低）

**CSV 表现**：
- 曲折比 > 2.0
- 路径明显绕大圈到达目标点

**根因**：
```
cost_penalty / cost_travel_multiplier 未设置（默认值偏低）
规划器倾向于走最短几何路径而非考虑障碍物代价
或 minimum_turning_radius 设得太大限制了路径灵活性
```

**推荐调整**：
```yaml
# nav.yaml planner_server.GridBased
cost_penalty: 2.0
cost_travel_multiplier: 2.0
```

#### 问题 4：路径急转弯（车辆跟不上）

**CSV 表现**：
- 某段 yaw_deg 突变 > 30°
- 对应 segment_dist 较小（说明在短距离内转了很大的角度）

**根因**：
```
规划的转弯半径小于车辆实际的 minimum_turning_radius（0.6m）
或 use_rotate_to_heading 未启用，车辆被迫边走边转
```

**推荐调整**：
```yaml
# nav.yaml planner_server.GridBased
minimum_turning_radius: 0.6（确保和车辆匹配）

# nav.yaml controller_server.FollowPath
use_rotate_to_heading: true
rotate_to_heading_min_angle: 0.785
```

---

## 三、分析工作流

### 3.1 标准分析步骤

```
步骤 1: 读取 CSV 元数据（# 头）
         → 了解本次路径的基本情况（点数、长度、目标点）

步骤 2: 加载数据列（跳过 # 行）
         → 读取 x, y, yaw_deg, segment_dist

步骤 3: 计算分析指标
         → 曲折比验证、角度突变检测、段间距分析

步骤 4: 绘制路径形状（可选）
         → x-y 散点图：观察路径是否平滑、有锯齿、贴墙

步骤 5: 诊断问题
         → 对照 2.3 节的典型问题匹配症状

步骤 6: 给出调参建议
         → 引用 nav.yaml 中的具体参数名和建议值
```

### 3.2 分析与调参的对应关系

```
📊 CSV 中看到的现象              🔧 应调整的参数
────────────────────────────────────────────────────
路径左右摇摆 / S 形          →  controller_server.FollowPath.lookahead_dist ↑
路径贴墙 / 距障碍物太近        →  costmap.inflation_radius ↑
路径大绕路 / 曲折比高         →  planner_server.GridBased.cost_penalty ↑
路径急转弯 / 角度突变大        →  planner_server.GridBased.minimum_turning_radius
整体路径毛糙 / 不平滑         →  smoother.w_smooth ↑ / w_data ↓
起点附近路径乱窜              →  AMCL 初始位姿不准 / 定位漂移
```

---

## 四、示例分析代码（供 AI 参考）

### 4.1 读取 CSV

```python
import csv
import math

def read_path_csv(filepath):
    """读取 plan_listener 生成的 CSV，返回元数据和点列表"""
    metadata = {}
    points = []

    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        for row in reader:
            if not row:
                continue
            if row[0].startswith("#"):
                # 解析元数据头
                line = ",".join(row)
                if ":" in line:
                    key_val = line.lstrip("# ").strip()
                    if "|" in key_val:
                        parts = key_val.split("|")
                        for p in parts:
                            if ":" in p:
                                k, v = p.split(":", 1)
                                metadata[k.strip()] = v.strip()
                    elif ":" in key_val:
                        k, v = key_val.split(":", 1)
                        metadata[k.strip()] = v.strip()
            else:
                # 解析数据行
                try:
                    pid = int(row[0])
                    x = float(row[1])
                    y = float(row[2])
                    yaw = float(row[3])
                    seg = float(row[4])
                    points.append({
                        "id": pid, "x": x, "y": y,
                        "yaw_deg": yaw, "segment_dist": seg
                    })
                except (ValueError, IndexError):
                    pass  # 跳过表头行

    return metadata, points
```

### 4.2 分析路径质量

```python
def analyze_path(metadata, points):
    """分析路径质量，返回诊断结果"""
    if len(points) < 2:
        return {"error": "路径点数太少"}

    # 1. 总长验证
    total_length = sum(p["segment_dist"] for p in points)

    # 2. 段间距一致性
    segs = [p["segment_dist"] for p in points if p["segment_dist"] > 0]
    if segs:
        mean_seg = sum(segs) / len(segs)
        var_seg = sum((s - mean_seg)**2 for s in segs) / len(segs)
        seg_cv = math.sqrt(var_seg) / mean_seg  # 变异系数
    else:
        seg_cv = 0

    # 3. 角度突变检测
    max_angle_change = 0
    sharp_turns = 0
    for i in range(1, len(points)):
        change = abs(points[i]["yaw_deg"] - points[i-1]["yaw_deg"])
        if change > 180:
            change = 360 - change
        if change > max_angle_change:
            max_angle_change = change
        if change > 15:
            sharp_turns += 1

    # 4. 估算转弯半径（角度变化大的地方）
    min_turn_radius = float("inf")
    for i in range(1, len(points)):
        angle_change_rad = abs(points[i]["yaw_deg"] - points[i-1]["yaw_deg"])
        if angle_change_rad > 180:
            angle_change_rad = 360 - angle_change_rad
        angle_change_rad = math.radians(angle_change_rad)
        if angle_change_rad > math.radians(1.0):  # 只计算有明显转弯的地方
            radius = points[i]["segment_dist"] / angle_change_rad
            if radius < min_turn_radius:
                min_turn_radius = radius

    # 5. 诊断
    diagnosis = []
    params_to_tune = []

    if seg_cv > 0.5:
        diagnosis.append("⚠️ 路径段间距不稳定，可能有锯齿/S形")
        params_to_tune.append(("lookahead_dist", "controller_server.FollowPath"))

    if max_angle_change > 15:
        diagnosis.append(f"⚠️ 存在急转弯（最大角度变化 {max_angle_change:.1f}°）")
        params_to_tune.append(("use_rotate_to_heading", "controller_server.FollowPath"))
        params_to_tune.append(("minimum_turning_radius", "planner_server.GridBased"))

    if min_turn_radius < 0.6:
        diagnosis.append(f"⚠️ 转弯半径 {min_turn_radius:.2f}m 小于车辆最小转弯半径 0.6m")
        params_to_tune.append(("minimum_turning_radius", "planner_server.GridBased"))

    total_len = metadata.get("总长", "?")
    detour = metadata.get("曲折比", "?")

    return {
        "total_length_m": total_length,
        "point_count": len(points),
        "seg_consistency": round(seg_cv, 3),
        "max_angle_change_deg": round(max_angle_change, 1),
        "sharp_turn_count": sharp_turns,
        "min_turn_radius_m": round(min_turn_radius, 3) if min_turn_radius != float("inf") else "N/A（纯直线）",
        "diagnosis": diagnosis,
        "params_to_tune": params_to_tune,
    }


def suggest_tuning(results):
    """根据诊断结果给出具体的 nav.yaml 调参建议"""
    suggestions = []

    for diag in results.get("diagnosis", []):
        if "S形" in diag or "锯齿" in diag:
            suggestions.append("""🔧 调整 controller_server.FollowPath:
  lookahead_dist: 0.3 → 0.7     （增大前视距离）
  min_lookahead_dist: 0.3 → 0.5
  max_lookahead_dist: 0.6 → 1.0
  use_velocity_scaled_lookahead_dist: true""")

        if "急转弯" in diag:
            suggestions.append("""🔧 调整 planner_server.GridBased:
  minimum_turning_radius: 0.6（确保匹配车辆物理能力）
  
  同时可启用原地旋转对准：
  controller_server.FollowPath.use_rotate_to_heading: true
  controller_server.FollowPath.rotate_to_heading_min_angle: 0.785""")

    if results.get("min_turn_radius_m") != "N/A（纯直线）" and results.get("min_turn_radius_m", 0) < 0.6:
        suggestions.append("""🔧 路径存在超出车辆能力的急弯，建议：
  planner_server.GridBased.minimum_turning_radius: 0.6
  Smoother.w_smooth: 0.5 → 0.7（增加平滑度）""")

    if not suggestions:
        suggestions.append("✅ 路径质量正常，无需调整")

    return suggestions
```

### 4.3 分析结论输出模板

当分析完一个 CSV 文件后，AI 应按以下模板输出结论：

```
═══════════════════════════════════════════
🗺️  路径分析报告
   文件: plan_0003_20260607_143022.csv
═══════════════════════════════════════════

📋 基本信息
  目标点: (3.13, -0.56) 朝向 176.2°
  路径点数: 287 | 总长: 15.83m
  曲折比: 13.53x | 弯曲度: 中等（含缓弯）

📊 量化指标
  段间距一致性: 0.245（良好）
  最大角度变化: 12.3°（正常）
  急弯数量: 0
  最小转弯半径: 0.85m（安全）

🔍 诊断结论
  ✅ 路径平滑，无异常锯齿
  ✅ 无急转弯，转弯半径满足车辆约束
  ⚠️ 曲折比偏高，路径稍绕，可考虑微调 cost_penalty

🔧 调参建议（按优先级）
  1. planner_server.GridBased.cost_penalty: 2.0
     → 让路径更居中，减少绕路

📝 备注
  路径整体质量良好，无需大改。
═══════════════════════════════════════════
```

---

## 五、常见问答

### Q1: 一条路径曲折比很大，一定是参数问题吗？

不一定。曲折比大可能是：
1. **正常避障**：路径绕过了障碍物（此时曲折比大是正常的）
2. **参数问题**：代价地图参数导致路径过度绕路
3. **起点终点重合**：如果起点终点很近但规划了长路径，曲折比会极大

> 判断方法：用 x/y 列画散点图，看路径形状是否合理。

### Q2: 连续几条 CSV 的起点为什么不一样？

每次导航的起点是车辆当前所在位置。如果路径 1 跑完时停在了 (3.0, -0.5)，下次规划的起点就是这个位置。所以 CSV 的起点坐标反映了车辆**当时**的实际位置。

### Q3: yaw_deg 的变化趋势能看出什么？

- yaw_deg **持续平稳变化**（如 175°→176°→177°）→ 正常转弯
- yaw_deg **来回震荡**（如 175°→178°→174°→179°）→ 路径锯齿，前视距离太小
- yaw_deg **突然跳变 180°** → 车辆进行了掉头或 Reeds-Shepp 的倒车 maneuver
- yaw_deg **长时间不变** → 直道行驶

### Q4: segment_dist 能看出什么？

- segment_dist **普遍较大**（> 0.3m）→ 路径点稀疏，可能精度不够
- segment_dist **普遍较小**（< 0.01m）→ 路径点过密，计算量大，冗余
- segment_dist **忽大忽小** → 路径点分布不均匀，可能平滑器参数不佳
- 正常值：`0.02~0.10m`（取决于地图分辨率和路径曲率）

### Q5: 多条 CSV 综合对比能发现什么？

对比同一场比赛中的多条路径 CSV：
- 如果所有路径的**起点和终点逐渐偏移** → 定位漂移（AMCL 问题）
- 如果**特定区域的路径总是不稳定** → 该区域地图质量问题或激光数据异常
- 如果**后面的路径比前面的更长** → 可能是电池电量下降导致机械响应变慢

---

## 六、关联文件参考

| 文件 | 用途 |
|------|------|
| `~/racecar/src/racecar/config/nav.yaml` | Nav2 全参数配置文件（所有建议调整的目标文件） |
| `~/racecar/path_records/plan_*.csv` | plan_listener 生成的路径记录（本技能的分析对象） |
| `~/racecar/src/racecar/scripts/go.py` | CSV 航点导航脚本（触发规划路径的上游） |
| `~/racecar/src/racecar/scripts/out_test.csv` | 预制航点 CSV（go.py 读取的输入文件） |
| `~/racecar/src/racecar/maps/ai_map.yaml` | 地图元数据（路径坐标系的基准） |

> 本技能文件位置：`<项目根>/skills/path-analysis-assistant.md`
> 对应的数据采集工具：`<项目根>/scripts/plan_listener.py`
> 部署与验证流程：`<项目根>/SOP-plan_listener注入与验证.md`
