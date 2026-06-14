---
title: Computer Vision for Robotics
tags: [computer-vision, robotics, ai, python]
---

# Computer Vision for Robotics

Applying computer vision techniques to robotic systems.

## Core Techniques

- **Visual SLAM** — ORB-SLAM3, RTAB-Map
- **Camera Calibration** — intrinsic/extrinsic parameters
- **Feature Detection** — SIFT, ORB, FAST corner detection
- **Object Detection** — YOLO, SSD, Faster R-CNN

## Hardware

- Raspberry Pi Camera Module v3
- Intel RealSense depth cameras
- OAK-D spatial AI camera

## Implementation

Vision pipelines run on [[Raspberry Pi Cluster]] using [[Machine Learning Fundamentals]] models. The processed data is sent to [[ESP32-S3 Robot Controller]] via [[MQTT Protocol]].

## Python Libraries

- **OpenCV** — image processing and camera control
- **scikit-image** — scientific image analysis
- **YOLOv8** — real-time object detection
