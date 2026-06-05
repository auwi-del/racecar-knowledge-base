#!/usr/bin/env python3
"""Convert rosbag2 with /image_raw to MP4 video."""
import sys
import cv2
import numpy as np
from rclpy.serialization import deserialize_message
from rosbag2_py import SequentialReader, StorageOptions, ConverterOptions
from sensor_msgs.msg import Image
from cv_bridge import CvBridge

bag_path = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser("~/recording_500s")
output_path = sys.argv[2] if len(sys.argv) > 2 else os.path.expanduser("~/recording_500s.mp4")

storage_options = StorageOptions(uri=bag_path, storage_id="sqlite3")
converter_options = ConverterOptions(input_serialization_format="cdr", output_serialization_format="cdr")
reader = SequentialReader()
reader.open(storage_options, converter_options)

topic_types = reader.get_all_topics_and_types()
type_map = {t.name: t.type for t in topic_types}

bridge = CvBridge()
writer = None
frame_count = 0
fps = 15

while reader.has_next():
    topic, data, t = reader.read_next()
    if topic == "/image_raw":
        try:
            msg = deserialize_message(data, Image)
            cv_img = bridge.imgmsg_to_cv2(msg, "bgr8")
            h, w = cv_img.shape[:2]
            if writer is None:
                fourcc = cv2.VideoWriter_fourcc(*"mp4v")
                writer = cv2.VideoWriter(output_path, fourcc, fps, (w, h))
            writer.write(cv_img)
            frame_count += 1
            if frame_count % 500 == 0:
                print(f"  Processed {frame_count} frames...")
        except Exception as e:
            print(f"  Error on frame {frame_count}: {e}")

if writer:
    writer.release()
print(f"\nDone! {frame_count} frames written to {output_path}")
