---
name: lookahead-tune
description: 查询/修改 davinci-mini Nav2 前视距离 (lookahead_dist)，修改后自动验证并给出建议
command: lookahead
---

## 任务

在线调整 davinci-mini 在 `nav.sh` + `go.py` 导航时的前视距离（lookahead_dist）。支持查询当前值、修改到指定值、恢复默认值，修改后自动验证并记录归档。

**适合这种场景**：小车直道左右晃、过弯太冲或转不过去、走起来犹豫。这是调参第一步，效果立竿见影。

## 固定参数

| 参数 | 值 |
|------|-----|
| 开发板 IP | 192.168.5.100 |
| 用户名 | davinci-mini |
| SSH 方式 | 密钥认证（免密） |
| 控制器节点 | `/controller_server` |
| 参数名 | `FollowPath.lookahead_dist` |
| 配套参数 | `FollowPath.min_lookahead_dist`, `FollowPath.max_lookahead_dist` |
| 默认值 | `0.3` |

## 执行步骤

### 前置检查

```bash
ssh davinci-mini@192.168.5.100 "echo connected" 2>/dev/null
```

如果连接失败，先运行 `connect-davinci` skill。

检查控制器节点是否在运行（nav.sh 没启动就没法调）：

```bash
ssh davinci-mini@192.168.5.100 "source /opt/ros/humble/setup.bash && source ~/racecar/install/setup.bash && ros2 node list 2>/dev/null | grep -q controller_server && echo 'controller OK' || echo 'controller NOT running — 请先运行 nav.sh'"
```

如果节点不在线，提示用户先启动 nav.sh，中止流程。

### 解析参数

根据传入的 `{{args}}` 分支处理：

- **无参数 / "query"** → 仅查询当前值
- **数字（如 0.5, 0.7）** → 将 lookahead_dist 设为该值
- **"reset" / "default"** → 恢复默认值 0.3

### 查询当前值

```bash
ssh davinci-mini@192.168.5.100 "source /opt/ros/humble/setup.bash && source ~/racecar/install/setup.bash && ros2 param get /controller_server FollowPath.lookahead_dist && ros2 param get /controller_server FollowPath.min_lookahead_dist && ros2 param get /controller_server FollowPath.max_lookahead_dist"
```

如果参数不存在或节点离线，报错并中止。

### 修改值（仅 set/reset 时需要）

验证值是否在合理范围（0.1 ~ 2.0）。如果超出范围，拒绝并提示合理范围。

```bash
ssh davinci-mini@192.168.5.100 "source /opt/ros/humble/setup.bash && source ~/racecar/install/setup.bash && ros2 param set /controller_server FollowPath.lookahead_dist NEW_VALUE"
```

其中 `NEW_VALUE` 为：
- 用户指定的值（set 模式）
- `0.3`（reset 模式）

### 善后处理（修改后自动执行）

每次修改后强制做以下验证和清理：

#### 1. 验证修改生效

```bash
ssh davinci-mini@192.168.5.100 "source /opt/ros/humble/setup.bash && source ~/racecar/install/setup.bash && ros2 param get /controller_server FollowPath.lookahead_dist 2>&1"
```

读取返回值，确认与期望值一致。不一致则重试一次，仍失败则报错。

#### 2. 检查配套约束

检查 `lookahead_dist` 是否被 `min_lookahead_dist` / `max_lookahead_dist` 钳位：

```bash
ssh davinci-mini@192.168.5.100 "source /opt/ros/humble/setup.bash && source ~/racecar/install/setup.bash && ros2 param get /controller_server FollowPath.min_lookahead_dist && ros2 param get /controller_server FollowPath.max_lookahead_dist"
```

如果 `lookahead_dist < min_lookahead_dist`，实际生效的是 `min_lookahead_dist`。告知用户这一情况，建议同步调小 `min_lookahead_dist`。

如果 `lookahead_dist > max_lookahead_dist`，且 `use_velocity_scaled_lookahead_dist` 为 true，实际前视距离会被速度缩放公式限制，告知用户这一点。

#### 3. 归档本次修改记录

```bash
ssh davinci-mini@192.168.5.100 "echo \"[$(date '+%Y-%m-%d %H:%M:%S')] lookahead_dist = NEW_VALUE (by lookahead-tune skill)\" >> /tmp/lookahead_tune_history.log && echo 'logged'"
```

#### 4. 向用户报告

报告格式：

```
前视距离调整完成 ✅

修改:
  FollowPath.lookahead_dist  旧值 → 新值
  FollowPath.min_lookahead_dist  当前值
  FollowPath.max_lookahead_dist  当前值

验证:
  ROS 参数已生效: ✅
  约束检查: ✅ (未被钳位) 或 ⚠️ (被 min/max 钳位，实际生效值为 X)

⚠️ 注意: 当前修改仅运行时生效，重启 nav.sh 后恢复为 YAML 文件值

永久修改:
  nano ~/racecar/src/racecar/config/nav.yaml
  搜索 "lookahead_dist"，修改后重启 nav.sh
  或使用 /lookahead save 将当前值写入 YAML（待实现）

参考:
  调参指南: 15-navigation-tuning-guide.md
```

### 5. 保存模式（可选扩展 — save）

如果用户传入 `save`，将当前运行时的 lookahead_dist 写入 YAML 文件变为永久：

```bash
ssh davinci-mini@192.168.5.100 "CURRENT=\$(source /opt/ros/humble/setup.bash && source ~/racecar/install/setup.bash && ros2 param get /controller_server FollowPath.lookahead_dist 2>/dev/null | grep -oP '[\d.]+(?=\s*$)' | tail -1); sed -i 's/^\([[:space:]]*lookahead_dist:\)[[:space:]]*[0-9.]*/\1 '"'"'\$CURRENT'"'"'/' ~/racecar/src/racecar/config/nav.yaml && echo 'saved to nav.yaml: lookahead_dist = '\$CURRENT"
```

注意：只有第一次 `save` 需要实现，本次 skill 先实现 query/set/reset 核心功能。

## 参数说明

| 参数 | 类型 | 说明 | 默认值 |
|------|------|------|--------|
| query | string | 查询当前值，不修改 | — |
| reset | string | 恢复默认值 0.3 | — |
| `<number>` | float | 设为指定值（0.1~2.0） | — |

**没传参数 = query 模式。**

## 注意事项

- 前视距离并非越大越好：太小 → 晃动；太大 → 切弯（走捷径撞墙）
- 本 skill 只修改 `lookahead_dist` 本身，不改 `min/max_lookahead_dist` —— 但会检查配套约束
- 修改仅运行时生效，重启 nav.sh 会回到 YAML 文件的配置值
- 修改历史记录在板上的 `/tmp/lookahead_tune_history.log`
- 本 skill 依赖 `connect-davinci` skill（如果 SSH 未连接）
