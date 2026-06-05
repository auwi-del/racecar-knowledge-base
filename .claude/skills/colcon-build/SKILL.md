---
name: colcon-build
description: 在 davinci-mini 开发板上编译 ROS2 工作区（colcon build），支持全量编译和单包编译
command: colcon
disable-model-invocation: true
---

## 任务

在 davinci-mini 开发板（192.168.5.100）上执行 `colcon build` 编译 ROS2 工作区，并报告编译结果。

## 固定参数

| 参数 | 值 |
|------|-----|
| 开发板 IP | 192.168.5.100 |
| 用户名 | davinci-mini |
| SSH 方式 | 密钥认证（免密）✅ |
| 工作区路径 | `~/racecar` |
| ROS2 版本 | Humble |

## 执行步骤

### 1. 解析参数

根据传入的 `{{args}}` 分支处理：

- **无参数 / 空字符串** → **默认编译 racecar 包**：`colcon build --packages-select racecar`
- **包名（如 racecar, nav2_waypoint_cycle）** → 只编译指定包：`colcon build --packages-select <包名>`
- **"all"** → 全量编译全部包
- **"clean"** → 先清理再全量编译：`colcon build --cmake-clean-first`
- **"force"** → 忽略错误继续编译：`colcon build --continue-on-error`

### 2. 前置检查

SSH 连通性检查：

```bash
ssh davinci-mini@192.168.5.100 "echo connected" 2>/dev/null
```

如果连接失败，先运行 `connect-davinci` skill。

### 3. 执行编译

根据参数决定编译命令：

```bash
ssh davinci-mini@192.168.5.100 "cd ~/racecar && source /opt/ros/humble/setup.bash && colcon build [OPTIONS] 2>&1"
```

其中 `[OPTIONS]` 根据参数替换为：
- 无参数 → `--packages-select racecar`（默认只编译 racecar 包）
- 单包名 → `--packages-select <包名>`
- all → 空（全量编译所有包）
- clean → `--cmake-clean-first`
- force → `--continue-on-error`

### 4. 解析编译结果

编译完成后，检查输出中的关键信息：

| 关键词 | 含义 |
|--------|------|
| `Finished` | 编译完成 |
| `[processing]` | 正在编译的包 |
| `FAILED` | 编译失败 |
| `[ Skipped ]` | 跳过（无变更时） |
| `error:` / `Error` | 编译错误详情 |
| `warning:` | 编译警告 |

### 5. 向用户报告

#### 编译成功 ✅

```
colcon build 完成 ✅

编译方式: 全量 / 单包(<包名>)
结果: SUCCESS
用时: X分X秒

已完成包:
  - package_a  SUCCEEDED
  - package_b  SUCCEEDED

⚠️ 如果有警告(Warnings)，一并列出数量和关键警告
```

#### 编译失败 ❌

```
colcon build 失败 ❌

编译方式: 全量 / 单包(<包名>)
结果: FAILED
用时: X分X秒

失败包:
  - package_c  FAILED ← 展开错误信息

错误摘要:
  [粘贴关键报错信息 3-5 行]
  ...

建议排查:
  1. 检查语法错误或缺少依赖
  2. 运行 colcon build --packages-select <包名> 单独编译失败包看详细输出
  3. 检查 src/ 下对应包的 CMakeLists.txt / package.xml
```

#### 包状态说明

colcon 输出中每个包的状态：

| 标志 | 含义 |
|------|------|
| `===` 包名 (一遍编译) | 开始处理 |
| `>>>` | 编译进行中 |
| `Finished <<<` | ✅ 成功 |
| `Failed <<<` | ❌ 失败 |
| `Skipped <<<` | ⏭️ 跳过（无变更）|

### 6. 如果编译成功且涉及配置变更

如果本次编译是因为修改了 `src/` 下的 `.yaml` 或 `.py` 文件，特别提醒用户：

```
💡 提醒：编译已完成，但正在运行的导航栈仍使用旧配置
   需要重启 nav.sh 才能加载新编译的内容：
   bash ~/racecar/nav.sh
```

## 参数说明

| 参数 | 类型 | 说明 | 示例 |
|------|------|------|------|
| 无参数 | — | 默认编译 racecar 包 | `/colcon-build` |
| `<包名>` | string | 只编译指定包 | `/colcon-build racecar` |
| `all` | string | 全量编译所有包 | `/colcon-build all` |
| `clean` | string | 清理后全量编译 | `/colcon-build clean` |
| `force` | string | 忽略错误继续编译 | `/colcon-build force` |

## 注意事项

- 编译前确保 SSH 连通，否则编译会失败
- 编译时开发板负载会升高（Orin NX 全量编译约 16-20 负载），属正常现象
- **只改 `.py` Python 文件不需要编译**，直接重启节点即可生效
- **只改 `.yaml` 配置文件不需要编译**，但需要手动复制到 `install/` 或重启 nav.sh（install/ 里的文件才是运行时读取的）
- 编译 `colcon build --packages-select racecar` 通常只需 10-30 秒
- 如果编译中 ROS 节点正在运行，建议先停掉再编译（避免文件锁冲突）
