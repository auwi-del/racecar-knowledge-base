#!/bin/bash
set -e

# ===== X11 显示配置 =====
# 检测 Windows 主机 IP 用于 X11 回传
if [ -z "$DISPLAY" ]; then
    # 从 192.168.5.x 网段接口推测 Windows 主机 (.2)
    MY_IP=$(ip addr show eth1 2>/dev/null | grep -oP '192\.168\.5\.\d+' | head -1)
    if [ -n "$MY_IP" ]; then
        # Windows 主机通常是同网段的 .2
        export DISPLAY="192.168.5.2:0"
    else
        export DISPLAY="192.168.5.2:0"
    fi
fi
echo "[nav.sh] DISPLAY=$DISPLAY"

# ===== 禁用 Discovery Server，使用默认多播 =====
unset ROS_DISCOVERY_SERVER
unset FASTRTPS_DEFAULT_PROFILES_FILE

# ===== 杀掉所有旧 ROS 进程 =====
echo "[nav.sh] Stopping old processes..."
killall -9 rviz2 lslidar_driver_node component_container_isolated component_container_mt \
    nav2_waypoint_cycle ekf_node encoder_node joint_state_publisher talker listener \
    racecar_driver_node static_transform_publisher ros2 2>/dev/null || true
sleep 2

# ===== 加载环境 =====
source /opt/ros/humble/setup.bash
source ~/racecar/install/setup.bash

# ===== 启动底盘 + 传感器 =====
echo "[nav.sh] Starting chassis + sensors (Run_car)..."
ros2 launch racecar Run_car.launch.py &
RUN_CAR_PID=$!
sleep 8

# ===== 等待关键话题就绪 =====
echo "[nav.sh] Waiting for /scan..."
for i in $(seq 1 15); do
    if ros2 topic list 2>/dev/null | grep -q "/scan"; then
        echo "[nav.sh] /scan ready"
        break
    fi
    sleep 1
done

# ===== 启动导航栈 + rviz2 =====
echo "[nav.sh] Starting nav2 stack + rviz2 (Run_nav)..."
ros2 launch racecar Run_nav.launch.py &
RUN_NAV_PID=$!

echo "[nav.sh] All launched. Waiting for rviz2 to appear on your screen..."
echo "[nav.sh] Run_car PID=$RUN_CAR_PID  Run_nav PID=$RUN_NAV_PID"

# 等待任意子进程退出
wait $RUN_CAR_PID $RUN_NAV_PID 2>/dev/null || true
