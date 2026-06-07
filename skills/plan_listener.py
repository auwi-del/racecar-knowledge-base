#!/usr/bin/env python3
"""
/plan 话题监听器 —— 配合 go.py 使用，实时打印 + 明文保存 Nav2 规划器输出的路径数据

功能：
  1. 监听 /plan 话题，每次收到新路径自动保存为明文 CSV
  2. 监听 /goal_pose，记录目标点信息
  3. 监听 /initialpose，记录初始位姿设置
  4. 终端实时打印路径分析（点数、长度、弯曲度、曲折比）

保存的文件格式：
  <保存目录>/plan_<序号>_<时间戳>.csv

  每文件含：
    - 元数据头（# 开头，记录目标点、路径统计等）
    - 数据列：point_id, x, y, yaw_deg, segment_dist

用法（在开发板上）：
    # 终端1：启动导航
    bash ~/racecar/nav.sh

    # 终端2：启动本监听器
    ros2 run racecar plan_listener

    # 终端3：启动 go.py 发航点
    ros2 run racecar go

    可选参数：
      --save-dir <路径>  指定保存目录（默认: ~/racecar/path_records/）
      --no-save          不保存文件，仅终端输出（兼容旧行为）

输出示例：
    ────────────────────────────────────────────
    🎯 收到新航点目标: (3.13, -0.56) 朝向 176.2°
    🗺️  收到新全局路径 | 帧: map | 点数: 287
       路径长度: 15.83 m
       起点: (1.96, -0.29) → 终点: (3.13, -0.56)
       💾 已保存: ~/racecar/path_records/plan_003_20260607_143022.csv
    ────────────────────────────────────────────
"""

import math
import os
import sys
import time
import argparse
from datetime import datetime

import rclpy
from rclpy.node import Node
from nav_msgs.msg import Path
from geometry_msgs.msg import PoseStamped, PoseWithCovarianceStamped


# ═══════════════════════════════════════════════
# 数学工具函数
# ═══════════════════════════════════════════════

def quaternion_to_yaw(q):
    """四元数 → 偏航角（弧度）"""
    siny_cosp = 2.0 * (q.w * q.z + q.x * q.y)
    cosy_cosp = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
    return math.atan2(siny_cosp, cosy_cosp)


def yaw_to_degrees(yaw):
    """弧度 → 度（0~360 显示）"""
    deg = math.degrees(yaw)
    return deg if deg >= 0 else deg + 360.0


def distance_2d(a, b):
    """二维欧氏距离"""
    return math.hypot(b.x - a.x, b.y - a.y)


def compute_path_length(poses):
    """计算路径总长度（二维）"""
    if len(poses) < 2:
        return 0.0
    total = 0.0
    for i in range(1, len(poses)):
        total += distance_2d(poses[i - 1].pose.position, poses[i].pose.position)
    return total


def estimate_curvature_changes(poses):
    """估算路径弯曲程度"""
    if len(poses) < 5:
        return "未知（点数太少）"

    sample_step = max(1, len(poses) // 20)
    total_angle_change = 0.0
    count = 0

    for i in range(sample_step, len(poses) - sample_step, sample_step):
        dx1 = poses[i].pose.position.x - poses[i - sample_step].pose.position.x
        dy1 = poses[i].pose.position.y - poses[i - sample_step].pose.position.y
        dx2 = poses[i + sample_step].pose.position.x - poses[i].pose.position.x
        dy2 = poses[i + sample_step].pose.position.y - poses[i].pose.position.y

        angle1 = math.atan2(dy1, dx1)
        angle2 = math.atan2(dy2, dx2)
        diff = abs(angle2 - angle1)
        if diff > math.pi:
            diff = 2.0 * math.pi - diff
        total_angle_change += diff
        count += 1

    if count == 0:
        return "未知"

    avg_change = math.degrees(total_angle_change / count)

    if avg_change < 5.0:
        return "较小（直道为主）"
    elif avg_change < 15.0:
        return "中等（含缓弯）"
    elif avg_change < 30.0:
        return "较大（含急弯）"
    else:
        return "很大（连续S弯/掉头）"


def make_save_dir(save_dir):
    """确保保存目录存在"""
    os.makedirs(save_dir, exist_ok=True)


def format_timestamp_for_filename():
    """生成文件名用的时间戳: YYYYMMDD_HHMMSS"""
    return datetime.now().strftime("%Y%m%d_%H%M%S")


# ═══════════════════════════════════════════════
# 主节点类
# ═══════════════════════════════════════════════

class PlanListener(Node):
    """监听 /plan 和 /goal_pose，打印路径分析 + 明文保存"""

    def __init__(self, save_dir=None, enable_save=True):
        super().__init__("plan_listener")

        # === 参数 ===
        self.save_dir = save_dir
        self.enable_save = enable_save

        # === 状态缓存 ===
        self.last_plan_key = None      # 路径去重 key
        self.last_goal_key = None      # 目标点去重 key
        self.plan_count = 0            # 收到路径的序号
        self.goal_count = 0            # 收到目标的序号
        self.last_goal_info = None     # 最近一次目标（用于写入路径文件元数据）
        self.last_path_start = None    # 最近一次路径起点

        # === 订阅 ===
        self.sub_plan = self.create_subscription(
            Path, "/plan", self.plan_callback, 10
        )
        self.sub_goal = self.create_subscription(
            PoseStamped, "/goal_pose", self.goal_callback, 10
        )
        self.sub_initpose = self.create_subscription(
            PoseWithCovarianceStamped, "/initialpose", self.initpose_callback, 10
        )

        # === 启动横幅 ===
        self.get_logger().info("=" * 60)
        self.get_logger().info("🗺️  /plan 监听器已启动")
        self.get_logger().info("   订阅话题: /plan /goal_pose /initialpose")

        if self.enable_save and self.save_dir:
            make_save_dir(self.save_dir)
            self.get_logger().info(f"   💾 保存目录: {self.save_dir}")
            self.get_logger().info("      格式: plan_<序号>_<时间戳>.csv (明文)")
        else:
            self.get_logger().info("   💾 保存: 关闭（仅终端输出）")

        self.get_logger().info("   配合 go.py / waypoint_cycle / RViz Nav Goal 使用")
        self.get_logger().info("=" * 60)

    # ─── 目标点回调 ─────────────────────────────

    def goal_callback(self, msg: PoseStamped):
        """收到新导航目标点"""
        px = msg.pose.position.x
        py = msg.pose.position.y
        yaw = quaternion_to_yaw(msg.pose.orientation)
        yaw_deg = yaw_to_degrees(yaw)

        self.goal_count += 1

        # 去重
        key = (round(px, 4), round(py, 4), round(yaw, 4))
        if key == self.last_goal_key:
            return
        self.last_goal_key = key

        # 缓存目标信息（供路径保存时写入元数据）
        self.last_goal_info = {
            "x": px,
            "y": py,
            "yaw_deg": yaw_deg,
            "frame": msg.header.frame_id,
            "index": self.goal_count,
        }

        self.get_logger().info("─" * 60)
        self.get_logger().info(
            f"🎯  [{self.goal_count}] 收到新航点目标 | "
            f"帧: {msg.header.frame_id}"
        )
        self.get_logger().info(
            f"    位置: ({px:.4f}, {py:.4f}) | "
            f"朝向: {yaw_deg:.1f}°"
        )

    # ─── 初始位姿回调 ───────────────────────────

    def initpose_callback(self, msg: PoseWithCovarianceStamped):
        """收到初始位姿设置"""
        px = msg.pose.pose.position.x
        py = msg.pose.pose.position.y
        yaw = quaternion_to_yaw(msg.pose.pose.orientation)
        yaw_deg = yaw_to_degrees(yaw)

        self.get_logger().info("─" * 60)
        self.get_logger().info(
            f"📍 初始位姿已设置 | "
            f"帧: {msg.header.frame_id}"
        )
        self.get_logger().info(
            f"    位置: ({px:.4f}, {py:.4f}) | "
            f"朝向: {yaw_deg:.1f}°"
        )

    # ─── 路径回调（核心）─────────────────────────

    def plan_callback(self, msg: Path):
        """收到新规划的全局路径 → 打印 + 保存"""
        poses = msg.poses
        if not poses:
            return

        self.plan_count += 1

        # === 去重 ===
        plan_key = self._make_plan_key(poses)
        if plan_key is not None and plan_key == self.last_plan_key:
            return
        self.last_plan_key = plan_key

        # === 计算路径统计 ===
        n_points = len(poses)
        total_len = compute_path_length(poses)
        start = poses[0].pose.position
        end = poses[-1].pose.position
        start_yaw = quaternion_to_yaw(poses[0].pose.orientation)
        end_yaw = quaternion_to_yaw(poses[-1].pose.orientation)
        curvature_desc = estimate_curvature_changes(poses)

        sec = msg.header.stamp.sec
        stamp_str = f"{sec}.{msg.header.stamp.nanosec:09d}"

        # 曲折比
        straight_dist = distance_2d(start, end)
        if straight_dist > 0.01:
            detour_ratio = total_len / straight_dist
        else:
            detour_ratio = 0.0

        # === 终端打印 ===
        self.get_logger().info("─" * 60)
        self.get_logger().info(
            f"🗺️  [{self.plan_count}] 收到新全局路径 | "
            f"帧: {msg.header.frame_id} | "
            f"时间: {stamp_str}"
        )
        self.get_logger().info(
            f"    📊 统计: {n_points} 个路径点 | "
            f"总长: {total_len:.2f}m | "
            f"弯曲度: {curvature_desc}"
        )
        self.get_logger().info(
            f"    🟢 起点: ({start.x:.4f}, {start.y:.4f}) | "
            f"朝向: {yaw_to_degrees(start_yaw):.1f}°"
        )
        self.get_logger().info(
            f"    🔴 终点: ({end.x:.4f}, {end.y:.4f}) | "
            f"朝向: {yaw_to_degrees(end_yaw):.1f}°"
        )

        if straight_dist > 0.01:
            tag = ""
            if detour_ratio > 1.5:
                tag = "（绕路较多）"
            elif detour_ratio < 1.1:
                tag = "（路径直接）"
            else:
                tag = "（正常）"
            self.get_logger().info(
                f"    📐 直线距离: {straight_dist:.2f}m | "
                f"曲折比: {detour_ratio:.2f}x{tag}"
            )

        if n_points > 5:
            sample = "前3点: "
            for i in range(min(3, n_points)):
                p = poses[i].pose.position
                y = yaw_to_degrees(quaternion_to_yaw(poses[i].pose.orientation))
                sample += f"({p.x:.2f},{p.y:.2f},{y:.0f}°) "
            self.get_logger().info(f"    📍 {sample}")

        if self.plan_count > 1:
            self.get_logger().info("    🔄 路径已重新规划（可能是避障或接近目标后调整）")

        # === 明文保存 ===
        if self.enable_save and self.save_dir:
            filepath = self._save_plan_to_csv(
                poses, n_points, total_len, detour_ratio,
                curvature_desc, msg.header.frame_id,
                start, end, start_yaw, end_yaw
            )
            self.get_logger().info(f"    💾 已保存: {filepath}")

    # ─── 内部方法 ───────────────────────────────

    def _make_plan_key(self, poses):
        """生成路径去重 key（基于前 5 个点的坐标）"""
        if len(poses) < 1:
            return None
        key_parts = []
        for i in range(min(5, len(poses))):
            p = poses[i].pose.position
            key_parts.append((round(p.x, 3), round(p.y, 3)))
        return tuple(key_parts)

    def _save_plan_to_csv(self, poses, n_points, total_len, detour_ratio,
                          curvature_desc, frame_id,
                          start, end, start_yaw, end_yaw):
        """
        将路径点保存为明文 CSV 文件

        文件格式：
            # plan_listener 路径记录
            # 生成时间: 2026-06-07 14:30:22
            # 帧: map | 路径点数: 287 | 总长: 15.83m
            # 起点: (1.96, -0.29) | 终点: (3.13, -0.56)
            # 曲折比: 13.53x | 弯曲度: 中等（含缓弯）
            # 目标点: (3.13, -0.56) 朝向 176.2° (来自 /goal_pose 第3次)
            #
            # point_id, x, y, yaw_deg, segment_dist
            0, 1.9600, -0.2900, 175.3, 0.0000
            1, 2.0500, -0.3100, 176.2, 0.0912
            2, 2.1400, -0.3300, 177.0, 0.0918
            ...
        """
        timestamp = format_timestamp_for_filename()
        filename = f"plan_{self.plan_count:04d}_{timestamp}.csv"
        filepath = os.path.join(self.save_dir, filename)

        with open(filepath, "w", encoding="utf-8") as f:
            # ── 元数据头（# 注释行） ──
            f.write("# plan_listener 路径记录\n")
            f.write(f"# 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"# 帧: {frame_id} | 路径点数: {n_points} | 总长: {total_len:.2f}m\n")
            f.write(f"# 起点: ({start.x:.4f}, {end.y:.4f}) | 终点: ({end.x:.4f}, {end.y:.4f})\n")
            f.write(f"# 起点朝向: {yaw_to_degrees(start_yaw):.1f}° | 终点朝向: {yaw_to_degrees(end_yaw):.1f}°\n")

            if detour_ratio > 0:
                f.write(f"# 曲折比: {detour_ratio:.2f}x | 弯曲度: {curvature_desc}\n")

            if self.last_goal_info:
                g = self.last_goal_info
                f.write(f"# 目标点: ({g['x']:.4f}, {g['y']:.4f}) "
                        f"朝向 {g['yaw_deg']:.1f}° "
                        f"(来自 /goal_pose 第{g['index']}次)\n")

            f.write("#\n")

            # ── 表头 ──
            f.write("# point_id, x, y, yaw_deg, segment_dist\n")

            # ── 数据行 ──
            prev_pos = None
            for i, pose in enumerate(poses):
                p = pose.pose.position
                yaw = quaternion_to_yaw(pose.pose.orientation)
                yaw_deg = yaw_to_degrees(yaw)

                if prev_pos is not None:
                    seg_dist = distance_2d(prev_pos, p)
                else:
                    seg_dist = 0.0

                f.write(f"{i}, {p.x:.6f}, {p.y:.6f}, {yaw_deg:.2f}, {seg_dist:.6f}\n")
                prev_pos = p

        return filepath


# ═══════════════════════════════════════════════
# 入口
# ═══════════════════════════════════════════════

def parse_args():
    parser = argparse.ArgumentParser(
        description="🗺️  /plan 话题监听器 — 实时打印 + 明文保存 Nav2 路径数据"
    )
    parser.add_argument(
        "--save-dir",
        default=None,
        help="路径 CSV 保存目录（默认: ~/racecar/path_records/）"
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="不保存文件，仅终端输出"
    )
    return parser.parse_args()


def main():
    args = parse_args()

    # 确定保存目录
    if args.no_save:
        save_dir = None
        enable_save = False
    else:
        save_dir = args.save_dir
        if save_dir is None:
            home = os.path.expanduser("~")
            save_dir = os.path.join(home, "racecar", "path_records")
        enable_save = True

    rclpy.init()
    node = PlanListener(save_dir=save_dir, enable_save=enable_save)
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.get_logger().info("─" * 60)
        node.get_logger().info("👋 监听器已停止")
        if enable_save and save_dir:
            node.get_logger().info(f"   路径文件保存在: {save_dir}")
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
