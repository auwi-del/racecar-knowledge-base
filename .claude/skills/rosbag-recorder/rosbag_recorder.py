#!/usr/bin/env python3
"""
rosbag 录制器 —— 配合 go.py 使用，将 ROS 话题录制为 rosbag 文件

与 plan_listener.py 的关系：
  plan_listener.py → 监听 /plan，存明文 CSV（路径分析用）
  rosbag_recorder.py → 录制原始话题，存 rosbag（完整回放用）
  两者可同时运行，互不冲突，互补使用。

功能：
  1. 每次启动时自动创建 录制-<MMDD_HHMMSS>/ 目录
  2. 调用 ros2 bag record 录制指定话题到该目录
  3. 支持自定义录制话题列表
  4. Ctrl+C 优雅停止 bag 录制

文件结构：
  ~/racecar/path_records/录制-<MMDD_HHMMSS>/
  ├── plan_*.csv                ← plan_listener 生成的路径 CSV（如有同时运行）
  └── rosbag_<时间戳>/           ← 本脚本生成的 rosbag
      ├── rosbag_<时间戳>.db3
      └── metadata.yaml

用法（在开发板上）：
    # 终端1：启动导航
    bash ~/racecar/nav.sh

    # 终端2：启动 rosbag 录制器（默认录制 /plan /goal_pose /odom_combined /scan /car_cmd_vel）
    ros2 run racecar rosbag_recorder.py

    # 终端3：启动 go.py 发航点
    ros2 run racecar go

    可选参数：
      --dir <目录名>       自定义本次录制目录名（默认: 录制-MMDD_HHMMSS）
      --parent <路径>      录制的父目录（默认: ~/racecar/path_records/）
      --topics <话题列表>   录制的话题，逗号分隔（默认: 见下方）
      --all                录制所有话题（等同于 ros2 bag record -a）
      --duration <秒>      最长录制时长，超时自动停止（默认: 不限）
      --max-size <MB>      单个 bag 文件最大体积（默认: 500MB）
      --compress           启用 zstd 压缩
      --no-save            仅打印预览，不实际录制

默认录制话题：
  /plan, /goal_pose, /odom_combined, /scan, /car_cmd_vel, /tf, /tf_static

输出示例：
    ═══════════════════════════════════════════
    📦  rosbag 录制器已启动
       💾 本次录制: ~/racecar/path_records/录制-0607_150312/
       📋 录制话题: /plan /goal_pose /odom_combined /scan /car_cmd_vel /tf
    ═══════════════════════════════════════════
    📦  ros2 bag 进程已启动 (PID: 12345)
    💾 正在录制到: 录制-0607_150312/rosbag_20260607_150312/
    ...
    👋 录制已停止
    💾 rosbag 保存位置: .../录制-0607_150312/rosbag_20260607_150312/
    📊 录制统计: 45.2秒, 23.8MB, 6个话题
"""

import argparse
import os
import signal
import subprocess
import sys
import time
from datetime import datetime


# ═══════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════

def format_session_dirname():
    """生成会话目录名: 录制-MMDD_HHMMSS（与 plan_listener 一致）"""
    return datetime.now().strftime("录制-%m%d_%H%M%S")


def format_timestamp():
    """生成时间戳: YYYYMMDD_HHMMSS"""
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def format_timestamp_human():
    """生成可读时间戳: 2026-06-07 15:03:12"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def make_session_dir(parent_dir, session_name):
    """创建本次录制的会话目录（与 plan_listener 一致）"""
    session_path = os.path.join(parent_dir, session_name)
    os.makedirs(session_path, exist_ok=True)
    return session_path


def size_str_to_bytes(size_str):
    """将人类可读的大小转为 bytes，如 500MB → 524288000"""
    size_str = size_str.strip().upper()
    if size_str.endswith("KB"):
        return int(float(size_str[:-2]) * 1024)
    elif size_str.endswith("MB"):
        return int(float(size_str[:-2]) * 1024 * 1024)
    elif size_str.endswith("GB"):
        return int(float(size_str[:-2]) * 1024 * 1024 * 1024)
    else:
        return int(float(size_str))


def bytes_to_size_str(bytes_val):
    """将 bytes 转为人类可读大小"""
    if bytes_val < 1024:
        return f"{bytes_val}B"
    elif bytes_val < 1024 * 1024:
        return f"{bytes_val / 1024:.1f}KB"
    elif bytes_val < 1024 * 1024 * 1024:
        return f"{bytes_val / 1024 / 1024:.1f}MB"
    else:
        return f"{bytes_val / 1024 / 1024 / 1024:.2f}GB"


# ═══════════════════════════════════════════════
# ROS2 Bag 录制管理器
# ═══════════════════════════════════════════════

class RosbagRecorder:
    """
    管理 ros2 bag record 子进程的启停。
    不直接继承 rclpy Node（避免与 go.py / plan_listener 的 rclpy 冲突），
    通过 subprocess 调用 ros2 bag record CLI。
    """

    # 默认录制话题（与比赛导航强相关，且数据量适中）
    DEFAULT_TOPICS = [
        "/plan",
        "/goal_pose",
        "/odom_combined",
        "/scan",
        "/car_cmd_vel",
        "/tf",
        "/tf_static",
    ]

    def __init__(self, save_dir, session_name, topics, record_all=False,
                 max_duration=None, max_size_mb=500, enable_compress=False,
                 dry_run=False):
        self.save_dir = save_dir
        self.session_name = session_name
        self.topics = topics
        self.record_all = record_all
        self.max_duration = max_duration
        self.max_size_mb = max_size_mb
        self.enable_compress = enable_compress
        self.dry_run = dry_run

        self.process = None
        self.bag_dir = None  # rosbag 输出目录
        self.start_time = None
        self.end_time = None

    def start(self):
        """启动 ros2 bag record 子进程"""
        if self.dry_run:
            self._log("🟡 预览模式（--no-save），不实际启动录制")
            self._log(f"   将录制话题: {' '.join(self.topics)}")
            return True

        # 准备 rosbag 输出目录
        timestamp = format_timestamp()
        bag_name = f"rosbag_{timestamp}"
        self.bag_dir = os.path.join(self.save_dir, bag_name)
        os.makedirs(self.bag_dir, exist_ok=False)

        # 构建 ros2 bag record 命令
        cmd = ["ros2", "bag", "record"]

        if self.record_all:
            cmd.append("-a")
        else:
            cmd.extend(self.topics)

        # 输出到指定目录
        cmd.extend(["-o", self.bag_dir])

        # 最大 bag 文件大小
        if self.max_size_mb:
            cmd.extend(["--max-bag-size", str(self.max_size_mb * 1024 * 1024)])

        # 压缩
        if self.enable_compress:
            cmd.extend(["--compression-mode", "file", "--compression-format", "zstd"])

        # 录制时长（由本脚本的定时器控制，非 ros2 bag 参数）
        # ros2 bag 没有 --duration 参数，我们用外部定时器控制

        self._log(f"📦 启动 ros2 bag record...")
        self._log(f"   命令: {' '.join(cmd)}")
        self._log(f"   输出: {self.bag_dir}/")

        try:
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                preexec_fn=os.setsid if sys.platform != "win32" else None,
            )
            self.start_time = time.time()
            self._log(f"   进程 PID: {self.process.pid}")
            return True

        except FileNotFoundError:
            self._log("❌ 错误: 找不到 ros2 命令，请确保 ROS2 环境已 source")
            return False
        except Exception as e:
            self._log(f"❌ 错误: 启动失败 — {e}")
            return False

    def stop(self):
        """停止 ros2 bag record 子进程"""
        if self.process is None:
            return

        self.end_time = time.time()
        self._log("👋 正在停止 rosbag 录制...")

        try:
            # 发送 SIGINT (Ctrl+C) 给进程组，让 ros2 bag 优雅关闭
            if sys.platform == "win32":
                self.process.terminate()
            else:
                os.killpg(os.getpgid(self.process.pid), signal.SIGINT)

            # 等待进程退出（最多等 10 秒）
            try:
                self.process.wait(timeout=10)
                self._log("   进程已退出")
            except subprocess.TimeoutExpired:
                self._log("   进程未响应，强制终止")
                self.process.kill()
                self.process.wait()

        except ProcessLookupError:
            pass  # 进程已自然退出

        # 报告录制统计
        self._report_stats()
        self.process = None

    def is_running(self):
        """检查录制是否还在运行"""
        if self.process is None:
            return False
        return self.process.poll() is None

    def get_elapsed_time(self):
        """获取已录制时长（秒）"""
        if self.start_time is None:
            return 0.0
        return time.time() - self.start_time

    def get_bag_size(self):
        """估算 rosbag 目录大小（字节）"""
        if self.bag_dir is None or not os.path.exists(self.bag_dir):
            return 0
        total = 0
        for dirpath, dirnames, filenames in os.walk(self.bag_dir):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                try:
                    total += os.path.getsize(fp)
                except OSError:
                    pass
        return total

    def _report_stats(self):
        """打印录制统计"""
        if not self.start_time or not self.end_time:
            return

        duration = self.end_time - self.start_time
        bag_size = self.get_bag_size()

        self._log(f"📊 录制统计")
        self._log(f"   时长: {duration:.1f}秒")
        self._log(f"   大小: {bytes_to_size_str(bag_size)}")
        self._log(f"   话题: {len(self.topics)}个")
        self._log(f"   位置: {self.bag_dir}/")

    def _log(self, msg):
        """打印日志（带时间戳）"""
        ts = datetime.now().strftime("%H:%M:%S")
        print(f"[{ts}] {msg}")


# ═══════════════════════════════════════════════
# 入口
# ═══════════════════════════════════════════════

def parse_args():
    parser = argparse.ArgumentParser(
        description="📦  rosbag 录制器 — 将 ROS 话题录制为 rosbag，与 plan_listener.py 并存"
    )
    parser.add_argument(
        "--dir",
        default=None,
        help="本次录制目录名（默认: 录制-MMDD_HHMMSS，自动创建）"
    )
    parser.add_argument(
        "--parent",
        default=None,
        help="录制的父目录（默认: ~/racecar/path_records/）"
    )
    parser.add_argument(
        "--topics",
        default=None,
        help="录制的话题，逗号分隔（默认: /plan,/goal_pose,/odom_combined,/scan,/car_cmd_vel,/tf,/tf_static）"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="录制所有话题（等同于 ros2 bag record -a）"
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=None,
        help="最长录制时长（秒），超时自动停止"
    )
    parser.add_argument(
        "--max-size",
        type=int,
        default=500,
        help="单个 bag 文件最大体积 MB（默认: 500）"
    )
    parser.add_argument(
        "--compress",
        action="store_true",
        help="启用 zstd 压缩"
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="仅打印预览，不实际录制"
    )
    return parser.parse_args()


def main():
    args = parse_args()

    # ── 确定保存目录 ──
    if args.no_save:
        save_dir = None
        session_name = "预览模式"
    else:
        session_name = args.dir
        if session_name is None:
            session_name = format_session_dirname()

        parent_dir = args.parent
        if parent_dir is None:
            home = os.path.expanduser("~")
            parent_dir = os.path.join(home, "racecar", "path_records")

        save_dir = make_session_dir(parent_dir, session_name)

    # ── 确定录制话题 ──
    if args.all:
        topics = []
        record_all = True
        topic_display = "所有话题 (-a)"
    elif args.topics:
        topics = [t.strip() for t in args.topics.split(",") if t.strip()]
        record_all = False
        topic_display = " ".join(topics)
    else:
        topics = RosbagRecorder.DEFAULT_TOPICS
        record_all = False
        topic_display = " ".join(topics)

    # ── 打印启动横幅（与 plan_listener 风格一致） ──
    print("=" * 60)
    print("📦  rosbag 录制器已启动")
    print("   本脚本录制原始话题，与 plan_listener.py 互补共存")
    if save_dir:
        print(f"   💾 本次录制: {save_dir}/")
    else:
        print(f"   💾 预览模式（不保存）")
    print(f"   📋 录制话题: {topic_display}")
    if args.duration:
        print(f"   ⏱  最长录制: {args.duration}秒")
    print(f"   📦 格式: rosbag (.db3)")
    if args.compress:
        print("   🔒 压缩: zstd 已启用")
    print("=" * 60)

    # ── 创建录制器并启动 ──
    if args.no_save:
        # 预览模式：打印会录什么，不实际启动
        print()
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 🟡 预览模式")
        print(f"   将录制到: {parent_dir if 'parent_dir' in dir() else '~/racecar/path_records/'}/{session_name}/")
        print(f"   话题列表:")
        for i, t in enumerate(topics if record_all else topics, 1):
            print(f"     {i:2d}. {t}")
        if record_all:
            print("     (所有话题)")
        print()
        print("✅ 预览完成。去掉 --no-save 实际运行。")
        return

    recorder = RosbagRecorder(
        save_dir=save_dir,
        session_name=session_name,
        topics=topics,
        record_all=record_all,
        max_duration=args.duration,
        max_size_mb=args.max_size,
        enable_compress=args.compress,
    )

    if not recorder.start():
        sys.exit(1)

    # ── 等待录制结束 ──
    try:
        while recorder.is_running():
            # 检查是否超时
            if args.duration and recorder.get_elapsed_time() >= args.duration:
                print(f"\n[{datetime.now().strftime('%H:%M:%S')}] ⏱  录制时长已达 {args.duration}秒，自动停止")
                break

            # 定期打印状态（每 30 秒）
            elapsed = recorder.get_elapsed_time()
            if int(elapsed) % 30 == 0 and int(elapsed) > 0:
                bag_size = recorder.get_bag_size()
                print(f"[{datetime.now().strftime('%H:%M:%S')}] ⏳ 录制中... "
                      f"{elapsed:.0f}秒 | {bytes_to_size_str(bag_size)}")

            time.sleep(1)

    except KeyboardInterrupt:
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 👋 收到停止信号")

    finally:
        recorder.stop()

    # ── 友好提示 ──
    if recorder.bag_dir:
        rel_path = os.path.relpath(recorder.bag_dir, os.path.dirname(recorder.save_dir))
        print(f"\n💡 提示:")
        print(f"   回放 rosbag:  ros2 bag play {recorder.bag_dir}")
        print(f"   查看 bag 信息: ros2 bag info {recorder.bag_dir}")
        print(f"   分析路径同时可运行: ros2 run racecar plan_listener.py --no-save")


if __name__ == "__main__":
    main()
