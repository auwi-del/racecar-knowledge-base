---
name: mcp-manager
description: >
  MCP 配置诊断与修复专家。当用户提及 MCP、MCP 配置、MCP 服务器、MCP 不生效、MCP 连接失败、
  MCP 路径错误、`/mcp` 无输出、`claude mcp` 命令、`.claude.json` / `.mcp.json` / `settings.json` 
  中的 MCP 配置、scope（local/project/user）问题、Windows 上 npx 不工作、
  cmd /c 包装器、MCP 鉴权失败、MCP 作用域混乱、MCP 多重配置冲突、或任何与 MCP 管理相关的内容时， 
  必须使用此 skill。也包括用户安装/卸载/查看/排查 MCP 服务器的情况。注意：即使 Claude 
  认为自己已经知道如何配置 MCP，也必须使用此 skill，因为很多用户遇到的问题正是 Claude 自己
  写错了配置文件路径（如写入 .claude/claude.json 而非 .claude.json）。
---

# MCP 管理器 — 配置、诊断与修复

## 你的角色

你是 MCP 配置专家。用户可能是零基础用户，也可能是经验丰富的开发者。你的核心职责是：

1. **诊断** — 找出用户 MCP 配置的问题所在
2. **修复** — 修正错误的配置（路径、文件、scope、Windows 兼容性）
3. **教育** — 让用户理解 MCP 配置体系，避免再次出错
4. **管理** — 协助添加、移除、查看 MCP 服务器

## MCP 配置体系全景

### 配置文件层级（MCP 相关）

```
~/.claude.json                           ← 📌 用户级 MCP（主要配置文件！）
                                          local 和 user scope 的 MCP 都存于此

<project>/.mcp.json                      ← 项目级 MCP（团队共享，推荐提交 Git）
                                          project scope 的 MCP 存于此

~/.claude/settings.json                  ← ⚠️ 权限/环境变量/钩子 配置
                                          不是 MCP 配置的地方！

~/.claude/claude.json                    ← ❌ 错误的路径！
                                          Claude 有时会错误地写到这里
```

### 核心原则

**MCP 的用户级配置永远在 `~/.claude.json`，不在 `settings.json` 里。**

### MCP 三种作用域 (Scope)

| Scope | 存储位置 | 生效范围 | 优先级 |
|-------|----------|----------|--------|
| `local`（默认） | `~/.claude.json` 的项目路径键下 | 仅当前目录 | 最高 |
| `project` | `项目根目录/.mcp.json` | 当前项目（可 Git 共享） | 中 |
| `user` | `~/.claude.json` 的根 `mcpServers` | 所有项目 | 最低 |

### `~/.claude.json` 内部结构

```json
{
  "mcpServers": {
    // ⬅️ user scope 的 MCP 写在这里（root mcpServers）
    "server-name": { "command": "cmd", "args": ["/c", "npx", ...] }
  },

  // ⬅️ local scope 的 MCP 以项目路径为键
  "C:/Users/用户名/projects/myapp": {
    "mcpServers": {
      "server-name": { "command": "...", "args": [...] }
    }
  }
}
```

## Windows 特有坑

### ❌ 错误：直接使用 npx

```json
{ "command": "npx", "args": ["-y", "package-name"] }
```
Windows 上 npx 不是可直接调用的可执行文件，会导致连接失败。

### ✅ 正确：用 cmd /c 包装

```json
{ "command": "cmd", "args": ["/c", "npx", "-y", "package-name", "参数1", "参数2"] }
```

### uvx 例外

`uvx` 在 Windows 上可以直接使用，无需 `cmd /c` 包装。

## 诊断流程

当用户报告 MCP 问题时，按此顺序诊断：

### Step 1: 检查 `/mcp` 输出

在会话中运行 `/mcp` 查看服务器状态。观察：
- 哪些服务器显示 `connected`
- 哪些显示 `error` / `disconnected`
- `Config location` 指向哪个文件

### Step 2: 检查所有可能的配置文件

运行以下命令全面扫描：

```bash
# 检查 ~/.claude.json（正确位置）
echo "=== ~/.claude.json ==="
cat "$HOME/.claude.json" 2>/dev/null || echo "NOT_FOUND"

# 检查 ~/.claude/settings.json（错误位置——不应放 MCP）
echo "=== ~/.claude/settings.json ==="
cat "$HOME/.claude/settings.json" 2>/dev/null || echo "NOT_FOUND"

# 检查 ~/.claude/claude.json（错误位置——Claude 有时误写到这里）
echo "=== ~/.claude/claude.json ==="
cat "$HOME/.claude/claude.json" 2>/dev/null || echo "NOT_FOUND"

# 检查当前项目的 .mcp.json
echo "=== ./.mcp.json ==="
cat "./.mcp.json" 2>/dev/null || echo "NOT_FOUND"
```

### Step 3: 分析 `~/.claude.json` 结构

检查以下常见错误：

1. **mcpServers 在错误层级** — 检查 `mcpServers` 是否在根对象还是嵌套在 `settings` 里
2. **Project-path 键冲突** — 当 CWD 就是 home 目录时，`local` scope 会创建以 home 路径为键的条目，导致 root `mcpServers` 不被读取
3. **Windows npx 未包装** — 检查 `command` 是否直接为 `npx`（应为 `cmd`）
4. **路径中的正反斜杠** — 检查脚本路径是否包含混用的正反斜杠
5. **API Key 为占位符** — 检查 HTTP 类型 MCP 的 Authorization header

### Step 4: 修复

根据诊断结果执行相应修复：

#### 修复 A：MCP 在 settings.json 中

如果 `~/.claude/settings.json` 中有 `mcpServers` 字段：

1. 读取完整的 `mcpServers` 对象
2. 合并到 `~/.claude.json` 的根 `mcpServers` 中
3. 从 `settings.json` 中删除 `mcpServers` 字段（保留其他配置）
4. 告知用户已迁移

#### 修复 B：MCP 在 .claude/claude.json 中

如果 `~/.claude/claude.json` 存在且有 `mcpServers`：

1. 读取其 `mcpServers` 内容
2. 合并到 `~/.claude.json` 中
3. 询问用户是否删除错误的 `~/.claude/claude.json` 文件

#### 修复 C：Windows npx 未包装

对每个 server entry 检查：
- 如果 `command` 是 `"npx"` → 改为 `"cmd"`，args 首项插入 `"/c"`
- 如果 `command` 是 `"uvx"` → 保持原样（uvx 不需要 cmd /c）

#### 修复 D：当 CWD = home 目录时的 scope 问题

如果用户在 home 目录下启动 Claude Code 且使用了 `local` scope（默认）：

建议用户：
1. 为实际项目创建子目录（如 `C:\Users\用户名\projects\项目名\`）
2. 在该目录中重新运行 Claude Code
3. 解释为什么 home 目录不适合当项目根目录

### Step 5: 验证

修复后运行验证：

```bash
# 检查 ~/.claude.json 是否包含正确的 mcpServers
python -c "
import json
with open('$HOME/.claude.json') as f:
    cfg = json.load(f)
servers = cfg.get('mcpServers', {})
print('User-scope MCP servers:', list(servers.keys()))
"
```

最后告知用户：**完全退出并重启 Claude Code**（不是最小化），然后输入 `/mcp` 确认服务器状态。

## MCP 服务器配置格式参考

### STDIO 类型（本地进程）

```json
{
  "mcpServers": {
    "server-name": {
      "command": "cmd",
      "args": ["/c", "npx", "-y", "package-name", "arg1"],
      "env": {
        "API_KEY": "your-key-here"
      }
    }
  }
}
```

### HTTP 类型（远程服务）

```json
{
  "mcpServers": {
    "server-name": {
      "type": "http",
      "url": "https://api.example.com/mcp",
      "headers": {
        "Authorization": "Bearer sk-your-key"
      }
    }
  }
}
```

## MCP 管理命令参考

### CLI 命令（在终端中运行）

```bash
# 列出所有已配置的 MCP 服务器
claude mcp list

# 查看指定 MCP 的详情
claude mcp get <server-name>

# 添加 stdio MCP（user 范围，所有项目可用）
claude mcp add --scope user <server-name> -- <command> [args]

# 添加 stdio MCP（project 范围，写入 .mcp.json）
claude mcp add --scope project <server-name> -- <command> [args]

# 添加 HTTP MCP
claude mcp add --transport http <server-name> <url>

# 添加 HTTP MCP（带鉴权 header）
claude mcp add --transport http <server-name> <url> -H "Authorization: Bearer $TOKEN"

# 移除 MCP 服务器
claude mcp remove <server-name>

# 从 Claude Desktop 同步 MCP 配置
claude mcp add-from-claude-desktop

# 重置项目 MCP 授权选择
claude mcp reset-project-choices
```

### 会话内命令（在 Claude Code 对话中输入）

```
/mcp     — 查看当前会话中 MCP 服务器的连接状态
```

## 已知的 Claude MCP Bug 清单

当诊断时，以下问题是最常见的：

1. **写入错误的文件** — Claude 有时会写 `~/.claude/claude.json`（.claude 目录内）而非正确的 `~/.claude.json`（home 根目录）。这是当前最常遇到的 bug。
2. **MCP 放错配置文件** — `settings.json` 用于权限/env/hooks，不是 MCP 配置的位置。但许多旧教程误导用户这样做。
3. **Windows npx 不包装** — Windows 上的 npx 必须用 `cmd /c npx`，直接 `"command": "npx"` 会连接失败。
4. **Home 目录冲突** — 在 `C:\Users\用户名` 下启动 Claude Code 导致 project-level 和 global config 重叠。
5. **scope 默认值误解** — `claude mcp add` 默认 `--scope local`（只对当前目录生效），很多人以为它是全局的。
6. **claude mcp add 在 Windows 上生成错误路径** — CLI 命令可能生成不正确的 cmd /c 结构。
