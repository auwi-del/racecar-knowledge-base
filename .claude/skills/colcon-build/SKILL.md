---
name: colcon-build
description: 在 davinci-mini 开发板上编译 ROS2 工作区（colcon build），支持全量编译和单包编译
command: colcon
disable-model-invocation: true
---

## 任务

在 davinci-mini 开发板（192.168.5.100）上执行 `colcon build` 编译 ROS2 工作区。

## 用法

| 命令 | 说明 |
|------|------|
| `/colcon` | 默认编译 racecar 包 |
| `/colcon <包名>` | 只编译指定包 |
| `/colcon all` | 全量编译 |
| `/colcon clean` | 清理后全量编译 |
| `/colcon force` | 忽略错误继续编译 |

## 固化脚本

以下脚本已部署在开发板 `~/racecar/build.sh`。如果不存在，先创建它：

```bash
cat > /tmp/build.sh << 'SCRIPT'
#!/bin/bash
# build.sh — colcon build 一键编译脚本
# Usage: ./build.sh [package|all|clean|force]
set -e
cd ~/racecar
source /opt/ros/humble/setup.bash
source install/setup.bash 2>/dev/null || true

OPTIONS=""; LABEL=""
case "${1:-racecar}" in
  all)    LABEL="全量编译" ;;
  clean)  OPTIONS="--cmake-clean-first"; LABEL="清理后全量编译" ;;
  force)  OPTIONS="--continue-on-error"; LABEL="全量编译(忽略错误)" ;;
  *)      OPTIONS="--packages-select $1"; LABEL="单包($1)" ;;
esac

echo "=== COLCON_BUILD_START ==="
echo "MODE: ${LABEL}"
date "+START: %Y-%m-%d %H:%M:%S"
START_SEC=$SECONDS
colcon build $OPTIONS 2>&1; EC=$?
ELAPSED=$((SECONDS - START_SEC))
date "+END:   %Y-%m-%d %H:%M:%S"
echo "ELAPSED: ${ELAPSED}s"
echo "EXIT_CODE: ${EC}"
echo "=== COLCON_BUILD_END ==="
exit $EC
SCRIPT
chmod +x /tmp/build.sh
ssh davinci-mini@192.168.5.100 "cp /tmp/build.sh ~/racecar/build.sh && chmod +x ~/racecar/build.sh"
```

## 执行步骤

### 1. 检查 SSH 连接

```bash
ssh davinci-mini@192.168.5.100 "echo connected" 2>/dev/null
```

不通则提示先运行 `connect-davinci` skill。

### 2. 运行编译脚本

```bash
ssh davinci-mini@192.168.5.100 "cd ~/racecar && ./build.sh <参数> 2>&1"
```

`<参数>` 根据用户输入替换：
- 无参数 → 空（脚本默认 racecar）
- `all` / `clean` / `force` / 包名 → 直接传入

### 3. 读取结果并报告

从输出中提取标记行向用户汇报。

**编译成功：**

```
colcon build 完成 ✅
  方式: 单包(racecar) | 用时: 12s
  结果: SUCCESS
```

**编译失败：**

```
colcon build 失败 ❌
  方式: 单包(racecar) | 用时: 15s

  失败包:
    - racecar  FAILED

  关键报错:
    (贴 3-5 行核心报错)

  建议:
    1. 检查语法或缺少依赖
    2. 单独编译排查: /colcon racecar
```

### 4. 编译后提醒

如果编译涉及 `.yaml` / `.py` 之外的变更，提醒重启导航栈：

```
💡 提醒：编译完成，但运行中的导航栈仍用旧配置
   需重启 nav.sh 才能生效: bash ~/racecar/nav.sh
```

## 注意事项

- 只改 `.py` 不需编译，重启节点即可
- 只改 `.yaml` 不需编译，但需重启 nav.sh（`install/` 下才是运行时读取的）
- 编译前建议先停掉 ROS 节点，避免文件锁冲突
- 脚本已集成在工作区，也可直接 SSH 上板执行 `./build.sh`
