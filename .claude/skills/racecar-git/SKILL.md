---
name: racecar-git
description: Manage the racecar git repository on davinci-mini (192.168.5.100). SSH key auth. Scope: ONLY ~/racecar. ALL other git repos on the board are IGNORED unless the user explicitly requests them.
command: git
---

## Scope

- **Core repo:** `~/racecar` on davinci-mini@192.168.5.100 (SSH key auth)
- **Ignored repos:** `~/racecar/src`, `/usr/local/ctc_decoder`, `/usr/local/samples`, `/usr/local/ctc_decoder/swig/kenlm`, `/usr/local/ctc_decoder/swig/ThreadPool`, and any other git repos found on the system — unless the user explicitly mentions them by name or path.
- **Rule:** If the user says "git" without specifying a repo, assume they mean `~/racecar`.

## Available Operations

All commands are executed via SSH on the remote board:

### Status
```bash
ssh davinci-mini@192.168.5.100 "cd ~/racecar && git status"
```

### Diff (unstaged + staged)
```bash
ssh davinci-mini@192.168.5.100 "cd ~/racecar && git diff && echo '===STAGED===' && git diff --cached"
```

### Log (recent history)
```bash
ssh davinci-mini@192.168.5.100 "cd ~/racecar && git log --oneline -10"
```

### Full log with dates
```bash
ssh davinci-mini@192.168.5.100 "cd ~/racecar && git log --all --format='%h %ai %s'"
```

### Add files
```bash
ssh davinci-mini@192.168.5.100 "cd ~/racecar && git add <file1> <file2>"
```

### Commit
```bash
ssh davinci-mini@192.168.5.100 "cd ~/racecar && git commit -m '<message>'"
```

### Push / Pull
```bash
ssh davinci-mini@192.168.5.100 "cd ~/racecar && git push"
ssh davinci-mini@192.168.5.100 "cd ~/racecar && git pull"
```

### Branch
```bash
ssh davinci-mini@192.168.5.100 "cd ~/racecar && git branch -a"
```

## Trigger Conditions

Auto-invoke this skill when the user's intent matches:
- "/git" slash command
- "管理git仓库" / "管理当前git仓库"
- "提交一次git commit" / "提交一次git" / "提交代码"
- "git status" / "git diff" / "git log" / "git add" / "git push" / "git pull"
- Any message containing an intent to inspect, commit, push, pull, branch, or otherwise manage git
- "查看git状态" / "查看提交历史" / "推送代码"

## Anti-trigger

Do NOT trigger for repos outside `~/racecar` (e.g. `~/racecar/src`, `/usr/local/samples`, etc.) unless the user explicitly names those repos.

## Execution Steps

### 1. Understand the intent
Parse what git operation the user wants: status, diff, log, add, commit, push, pull, branch, etc.

### 2. Execute the operation
Run the appropriate SSH command from the operations list above.

### 3. Report results
Display the output clearly. If it's a commit, show:
- The commit hash and message
- Files changed
- Current status after commit

### 4. If user asks to commit
Always run `git status` and `git diff` first to show what will be committed, then confirm with the user before executing the commit.

### 5. Error handling
If SSH fails or the command errors, report the error clearly and suggest fixes.
