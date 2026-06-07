#!/usr/bin/env python3
"""
rosbag 录制器 —— 配合 go.py 使用，将 ROS 话题录制为 rosbag 文件

工作模式：
  1. 启动后进入【待机监听模式】，不录制，等待话题活动
  2. 监听到 /goal_pose 或 /plan 话题有数据时，自动从待机→录制
  3. Ctrl+C 停止录制，回到待机或退出
  4. 再次收到新目标时自动开始新一轮录制

与 plan_listener.py 的关系：
  plan_listener.py → 每次新路径存一个 CSV（结构化的路径分析数据）
  rosbag_recorder.py → 按"轮次"录制完整 rosbag（原始话题数据）
  两者可同时运行，互不冲突。

目录结构：
  ~/racecar/path_records/录制-<MMDD_HHMMSS>/
  ├── 轮次-001/              ← 第1次触发录制
  │   └── rosbag_<时间戳>/
  │       ├── *.db3
  │       └── metadata.yaml
  ├── 轮次-002/              ← 第2次触发录制
  │   └── rosbag_<时间戳>/
  └── plan_*.csv             ← plan_listener 生成的路径 CSV

用法（在开发板上）：
    # 终端1：启动导航
    bash ~/racecar/nav.sh

    # 终端2：启动 rosbag 录制器（待机监听中，等 go.py 发目标就自动录）
    ros2 run racecar rosbag_recorder.py

    # 终端3：启动 go.py 发航点（触发录制自动开始）
    ros2 run racecar go

    可选参数：
      --dir <目录名>       本次录制目录名（默认: 录制-MMDD_HHMMSS）
      --parent <路径>      录制的父目录（默认: ~/racecar/path_records/）
      --topics <话题列表>   录制的话题，逗号分隔（默认: 见下方）
      --all                录制所有话题
      --duration <秒>      单轮最长录制时长（默认: 不限）
      --max-size <MB>      单个 bag 最大体积（默认: 500MB）
      --compress           启用 zstd 压缩
      --trigger <话题>      触发录制的话题（默认: /goal_pose）
      --no-save            预览模式，不实际录制

默认录制话题：
  /plan, /goal_pose, /odom_combined, /scan, /car_cmd_vel, /tf, /tf_static

输出示例：
    ═══════════════════════════════════════════
    📦  rosbag 录制器 — 触发式录制
       💾 录制目录: path_records/录制-0607_171331/
       📋 话题: /plan /goal_pose /odom_combined /scan /car_cmd_vel /tf
       ⏳ 待机中... 等待 /goal_pose 或 /plan 有数据...
    ═══════════════════════════════════════════
    [17:15:00] 🎯 检测到 /goal_pose 活动 → 开始录制 轮次-001
    [17:15:00] 📦 ros2 bag record 已启动 (PID: 12345)
    [17:17:30] ⏹   /goal_pose 停止活动 → 停止录制 轮次-001
    [17:17:30] 💾 已保存: .../轮次-001/rosbag_20260607_171500/
    [17:17:30] ⏳ 待机中... 等待下一次触发...
    [17:18:00] 🎯 检测到 /goal_pose 活动 → 开始录制 轮次-002
"""

import argparse
import os
import signal
import subprocess
import sys
import threading
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


def format_time_human():
    """生成可读时间戳: [17:15:00]"""
    return datetime.now().strftime("%H:%M:%S")


def make_session_dir(parent_dir, session_name):
    """创建本次录制的会话目录"""
    session_path = os.path.join(parent_dir, session_name)
    os.makedirs(session_path, exist_ok=True)
    return session_path


def bytes_to_size_str(bytes_val):
    """将 bytes 转为人类可读大小"""
    if bytes_val is None or bytes_val < 0:
        return "0B"
    if bytes_val < 1024:
        return f"{bytes_val}B"
    elif bytes_val < 1024 * 1024:
        return f"{bytes_val / 1024:.1f}KB"
    elif bytes_val < 1024 * 1024 * 1024:
        return f"{bytes_val / 1024 / 1024:.1f}MB"
    else:
        return f"{bytes_val / 1024 / 1024 / 1024:.2f}GB"


# ═══════════════════════════════════════════════
# 话题活动检测器
# ═══════════════════════════════════════════════

class TopicMonitor:
    """
    通过 ros2 topic hz 检测目标话题是否有新数据。
    与 rclpy 无关，纯 subprocess 实现，与 plan_listener 零冲突。
    """

    def __init__(self, trigger_topics, check_interval=1.0, activity_window=3):
        """
        trigger_topics: 要监听的话题列表
        check_interval: 每次检测间隔（秒）
        activity_window: 连续几次检测有数据才算"活动" / 连续几次无数据才算"停止"
        """
        self.trigger_topics = trigger_topics
        self.check_interval = check_interval
        self.activity_window = activity_window

    @staticmethod
    def check_topic_publishers(topic):
        """
        检查指定话题是否有发布者（瞬间完成，无需等待数据）。
        用 ros2 topic info 查询发布者数量。
        """
        try:
            result = subprocess.run(
                ["ros2", "topic", "info", topic],
                capture_output=True, text=True, timeout=3
            )
            # "Publisher count: N" 且 N > 0 → 有发布者
            output = result.stdout + result.stderr
            for line in output.splitlines():
                if "Publisher count:" in line:
                    count_str = line.split(":")[-1].strip()
                    return int(count_str) > 0
            return False
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError,
                subprocess.SubprocessError, FileNotFoundError, ValueError):
            return False

    def wait_for_trigger(self, on_trigger, on_idle=None, stop_event=None):
        """
        持续检测话题活动。
        当检测到有数据时调用 on_trigger()，停止时调用 on_idle()。
        stop_event: threading.Event，设置后退出循环。
        """
        consecutive_active = 0
        consecutive_inactive = 0
        is_currently_recording = False

        while stop_event is None or not stop_event.is_set():
            any_active = False

            # 检查所有触发话题
            for topic in self.trigger_topics:
                if self.check_topic_publishers(topic):
                    any_active = True
                    break

            if any_active:
                consecutive_active += 1
                consecutive_inactive = 0
            else:
                consecutive_inactive += 1
                consecutive_active = 0

            # 判断状态转换
            if not is_currently_recording and consecutive_active >= self.activity_window:
                # 待机 → 录制
                is_currently_recording = True
                consecutive_inactive = 0
                if on_trigger:
                    on_trigger()

            elif is_currently_recording and consecutive_inactive >= self.activity_window:
                # 录制 → 待机（话题停止活动）
                is_currently_recording = False
                consecutive_active = 0
                if on_idle:
                    on_idle()

            time.sleep(self.check_interval)

        return is_currently_recording


# ═══════════════════════════════════════════════
# ROS2 Bag 录制管理器
# ═══════════════════════════════════════════════

class RosbagRecorder:
    """管理 ros2 bag record 子进程的启停"""

    # 默认录制话题
    DEFAULT_TOPICS = [
        "/plan",
        "/goal_pose",
        "/odom_combined",
        "/scan",
        "/car_cmd_vel",
        "/tf",
        "/tf_static",
    ]

    # 默认触发话题（检测到这些话题有数据就自动开始录制）
    DEFAULT_TRIGGER_TOPICS = [
        "/goal_pose",
        "/plan",
    ]

    def __init__(self, save_dir, topics, record_all=False,
                 max_duration=None, max_size_mb=500, enable_compress=False):
        self.save_dir = save_dir
        self.topics = topics if topics else self.DEFAULT_TOPICS
        self.record_all = record_all
        self.max_duration = max_duration
        self.max_size_mb = max_size_mb
        self.enable_compress = enable_compress

        self.process = None
        self.bag_dir = None
        self.round_number = 0   # 第几轮录制
        self.start_time = None
        self._lock = threading.Lock()

    @property
    def is_recording(self):
        return self.process is not None and self.process.poll() is None

    def start_recording(self):
        """开始新一轮录制"""
        with self._lock:
            if self.is_recording:
                return False  # 已经在录制了

            self.round_number += 1
            round_name = f"轮次-{self.round_number:03d}"
            round_dir = os.path.join(self.save_dir, round_name)
            os.makedirs(round_dir, exist_ok=True)

            timestamp = format_timestamp()
            bag_name = f"rosbag_{timestamp}"
            self.bag_dir = os.path.join(round_dir, bag_name)

            cmd = ["ros2", "bag", "record"]

            if self.record_all:
                cmd.append("-a")
            else:
                cmd.extend(self.topics)

            cmd.extend(["-o", self.bag_dir])
            cmd.extend(["--max-bag-size", str(self.max_size_mb * 1024 * 1024)])

            if self.enable_compress:
                cmd.extend(["--compression-mode", "file", "--compression-format", "zstd"])

            try:
                self.process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    preexec_fn=os.setsid if sys.platform != "win32" else None,
                )
                self.start_time = time.time()
                t = format_time_human()
                print(f"[{t}] 📦 开始录制 {round_name}")
                print(f"[{t}]    命令: {' '.join(cmd)}")
                print(f"[{t}]    PID: {self.process.pid}")
                return True
            except Exception as e:
                t = format_time_human()
                print(f"[{t}] ❌ 启动失败: {e}")
                return False

    def stop_recording(self):
        """停止当前录制"""
        with self._lock:
            if self.process is None:
                return

            if self.process.poll() is None:
                t = format_time_human()
                print(f"[{t}] ⏹  正在停止录制 轮次-{self.round_number:03d}...")

                try:
                    if sys.platform == "win32":
                        self.process.terminate()
                    else:
                        os.killpg(os.getpgid(self.process.pid), signal.SIGINT)

                    try:
                        self.process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        self.process.kill()
                        self.process.wait()
                except ProcessLookupError:
                    pass

                # 统计
                duration = time.time() - self.start_time if self.start_time else 0
                bag_size = self._get_bag_size()
                t = format_time_human()
                print(f"[{t}] 💾 已保存: {self.bag_dir}/")
                print(f"[{t}] 📊 轮次-{self.round_number:03d}: "
                      f"{duration:.0f}秒, {bytes_to_size_str(bag_size)}")

            self.process = None
            self.bag_dir = None

    def _get_bag_size(self):
        """估算当前 rosbag 目录大小"""
        if not self.bag_dir or not os.path.exists(self.bag_dir):
            return 0
        total = 0
        for dirpath, _, filenames in os.walk(self.bag_dir):
            for f in filenames:
                try:
                    total += os.path.getsize(os.path.join(dirpath, f))
                except OSError:
                    pass
        return total

    def cleanup(self):
        """安全停止录制"""
        self.stop_recording()


# ═══════════════════════════════════════════════
# 入口
# ═══════════════════════════════════════════════

def parse_args():
    parser = argparse.ArgumentParser(
        description="📦  rosbag 录制器 — 待机监听，检测到话题数据自动开始录制"
    )
    parser.add_argument(
        "--dir", default=None,
        help="本次录制目录名（默认: 录制-MMDD_HHMMSS）"
    )
    parser.add_argument(
        "--parent", default=None,
        help="录制的父目录（默认: ~/racecar/path_records/）"
    )
    parser.add_argument(
        "--topics", default=None,
        help="录制的话题，逗号分隔（默认: 6 个常用话题）"
    )
    parser.add_argument(
        "--all", action="store_true",
        help="录制所有话题"
    )
    parser.add_argument(
        "--trigger", default="/goal_pose,/plan",
        help="触发录制的话题，逗号分隔（默认: /goal_pose,/plan）"
    )
    parser.add_argument(
        "--duration", type=float, default=None,
        help="单轮最长录制时长（秒）"
    )
    parser.add_argument(
        "--max-size", type=int, default=500,
        help="单个 bag 文件最大体积 MB（默认: 500）"
    )
    parser.add_argument(
        "--compress", action="store_true",
        help="启用 zstd 压缩"
    )
    parser.add_argument(
        "--no-save", action="store_true",
        help="预览模式"
    )
    return parser.parse_args()


def main():
    args = parse_args()

    # ── 确定参数 ──
    session_name = args.dir or format_session_dirname()
    parent_dir = args.parent or os.path.join(
        os.path.expanduser("~"), "racecar", "path_records"
    )

    # 触发话题
    trigger_topics = [
        t.strip() for t in args.trigger.split(",") if t.strip()
    ]

    # 录制话题
    if args.all:
        record_topics = []
        record_all = True
        topic_display = "所有话题 (-a)"
    elif args.topics:
        record_topics = [t.strip() for t in args.topics.split(",") if t.strip()]
        record_all = False
        topic_display = " ".join(record_topics)
    else:
        record_topics = RosbagRecorder.DEFAULT_TOPICS
        record_all = False
        topic_display = " ".join(record_topics)

    # ── 创建保存目录 ──
    save_dir = make_session_dir(parent_dir, session_name) if not args.no_save else None

    # ── 启动横幅 ──
    print("=" * 60)
    print("📦  rosbag 录制器 — 触发式录制")
    print("   与 plan_listener.py 互补共存")
    if save_dir:
        print(f"   💾 录制目录: {save_dir}/")
    print(f"   📋 录制话题: {topic_display}")
    print(f"   🎯 触发话题: {' '.join(trigger_topics)}")
    print(f"   ⏳ 待机中... 等待话题活动...")
    if args.compress:
        print("   🔒 压缩: zstd")
    print("=" * 60)

    if args.no_save:
        print(f"\n[{format_time_human()}] 🟡 预览模式（去掉 --no-save 开启录制）")
        return

    # ── 初始化组件 ──
    recorder = RosbagRecorder(
        save_dir=save_dir,
        topics=record_topics if not record_all else None,
        record_all=record_all,
        max_duration=args.duration,
        max_size_mb=args.max_size,
        enable_compress=args.compress,
    )

    monitor = TopicMonitor(
        trigger_topics=trigger_topics,
        check_interval=1.0,
        activity_window=2,  # 连续检测到 2 次即触发
    )

    # ── 定义触发/停止回调 ──
    def on_trigger():
        t = format_time_human()
        print(f"[{t}] 🎯 检测到话题活动 → 开始录制")
        recorder.start_recording()

    def on_idle():
        t = format_time_human()
        print(f"[{t}] 🔇 话题停止活动 → 停止录制")
        recorder.stop_recording()
        print(f"[{t}] ⏳ 待机中... 等待下一次触发...")

    # ── 运行监听循环 ──
    stop_event = threading.Event()

    try:
        monitor.wait_for_trigger(
            on_trigger=on_trigger,
            on_idle=on_idle,
            stop_event=stop_event,
        )
    except KeyboardInterrupt:
        t = format_time_human()
        print(f"\n[{t}] 👋 收到停止信号")
    finally:
        recorder.cleanup()
        t = format_time_human()
        print(f"[{t}] ✅ 录制器已退出")
        print(f"[{t}] 💾 所有文件保存在: {save_dir}/")


if __name__ == "__main__":
    main()
