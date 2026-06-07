---
name: 路径分析助手
description: 分析 plan_listener.py 录制的 /plan 路径 CSV 文件：评估路径质量、诊断导航问题、给出 nav.yaml 调参建议
command: 路径分析
---

## 任务

读取并分析 `plan_listener.py` 生成的路径 CSV 文件，评估路径质量，诊断导航问题，输出带参数建议的分析报告。

## 触发场景

用户提供 `plan_*.csv` 文件或包含该文件的目录时自动触发。同时提供以下触发词：
- "分析路径"、"看路径"、"路径质量如何"
- "为什么路径这么绕/抖/贴墙"、"调什么参数"

## CSV 文件格式

| 列名 | 单位 | 说明 |
|:----:|:----:|:------|
| `point_id` | — | 路径点序号，从 0 开始 |
| `x` | 米 | 地图坐标系 X 坐标 |
| `y` | 米 | 地图坐标系 Y 坐标 |
| `yaw_deg` | 度 | 该点的朝向角（0~360°，正东 0°，逆时针增加） |
| `segment_dist` | 米 | 该点到上一个点的间距（第 0 行为 0） |

元数据行以 `#` 开头，包含：路径点数、总长、起点/终点坐标、曲折比、弯曲度、目标点信息。

## 分析框架（4 维度）

| 维度 | 指标 | 良好 | 警告 | 异常 |
|:----:|:----:|:----:|:----:|:----:|
| 平滑度 | 段间距变异系数 | < 0.3 | 0.3 ~ 0.5 | > 0.5 |
| 安全性 | 转弯半径 | > 0.6m | 0.3 ~ 0.6m | < 0.3m |
| 效率 | 曲折比 | < 1.2x | 1.2x ~ 1.5x | > 1.5x |
| 曲率 | 相邻点角度变化 | < 5° | 5° ~ 15° | > 15° |

## 执行步骤

### 1. 加载并解析 CSV

```python
import csv, math

def load_path_csv(filepath):
    meta, points = {}, []
    with open(filepath, encoding="utf-8") as f:
        for row in csv.reader(f):
            if not row: continue
            if row[0].startswith("#"):
                line = ",".join(row).lstrip("# ")
                for part in line.split("|"):
                    if ":" in part:
                        k, v = part.split(":", 1)
                        meta[k.strip()] = v.strip()
            else:
                try:
                    points.append({
                        "id": int(row[0]), "x": float(row[1]), "y": float(row[2]),
                        "yaw_deg": float(row[3]), "segment_dist": float(row[4])
                    })
                except: pass
    return meta, points
```

### 2. 计算量化指标

- `段间距变异系数` = segment_dist 标准差 ÷ 均值（>0.5 说明路径点分布不均，有锯齿）
- `最大角度变化` = max(abs(yaw_diff))，处理 360° 绕越（>15° 说明有急弯）
- `最小转弯半径` = min(seg_dist / abs(yaw_change_rad))，仅在角度变化 >1° 处计算（<0.6m 说明超出车辆能力）
- `曲折比` = 总长 / 起点到终点直线距离（来自元数据或重新计算）

### 3. 匹配典型问题

| 症状（CSV 表现） | 诊断 | 应调整的参数 |
|-----------------|------|-------------|
| yaw_deg 正负交替 / S 形 | 前视距离太小 | `controller_server.FollowPath.lookahead_dist` ↑ |
| 路径偏地图边缘 / 距障碍物近 | 膨胀半径不足 | `costmap.inflation_radius` ↑ |
| 曲折比 > 1.5 | 代价惩罚偏低 | `planner_server.GridBased.cost_penalty` ↑ |
| yaw_deg 突变 > 15° | 转弯半径约束不匹配 | `minimum_turning_radius` / `use_rotate_to_heading` |
| 段间距变异系数 > 0.5 | 平滑器参数不佳 | `smoother.w_smooth` ↑ / `w_data` ↓ |
| 路径点数 < 5 | 规划失败或目标太近 | `max_planning_time` / `tolerance` |

### 4. 输出分析报告

按以下模板输出：

```
═══════════════════════════════════════════
🗺️  路径分析报告
   文件: plan_0003_20260607_143022.csv
═══════════════════════════════════════════

📋 基本信息
  目标点: (x, y) 朝向 °
  路径点数: N | 总长: X.XXm
  曲折比: X.XXx | 弯曲度: 描述

📊 量化指标
  段间距一致性: X.XXX
  最大角度变化: X.X°
  急弯数量: N
  最小转弯半径: X.XXm

🔍 诊断结论
  ✅ / ⚠️ / ❌ 逐项列出

🔧 调参建议（按优先级）
  1. 参数名: 当前值 → 建议值
     说明：为什么这么改

📝 备注
  其他观察或建议
═══════════════════════════════════════════
```

### 5. 多文件对比分析（mode=compare 时）

对比同一场比赛中的多个 CSV：
- 如果所有路径的起点/终点逐渐偏移 → AMCL 定位漂移
- 如果特定区域路径总不稳定 → 该区域地图质量问题
- 如果后面路径比前面更长 → 可能是电池下降导致机械响应变慢

## 注意事项

- 路径 CSV 是 Nav2 规划的**全局路径**，不是车辆实际行驶轨迹
- 如果 `controller_server` 被注释，实际路径跟踪由 Python 脚本完成，CSV 路径与实际行驶可能有差异
- 路径质量分析应结合目标点位置、障碍物分布综合判断
- 该 skill 对应的数据采集脚本为 `plan_listener.py`，详见 plan-listener skill
