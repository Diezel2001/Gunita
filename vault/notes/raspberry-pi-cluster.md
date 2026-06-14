---
title: Raspberry Pi Cluster
tags: [raspberry-pi, distributed-computing, robotics, hardware]
---

# Raspberry Pi Cluster

A 4-node Raspberry Pi 5 cluster for distributed robotics computing.

## Hardware

- 4x Raspberry Pi 5 (8 GB model)
- 64 GB microSD cards per node
- Gigabit Ethernet switch
- Custom 3D-printed stacking case with cooling fans

## Software Stack

- **Docker Swarm** for container orchestration
- **K3s** lightweight Kubernetes as alternative
- Shared NFS storage via [[Docker Container Deployment]]

## Use Cases

The cluster handles:
- Real-time computer vision inference using [[Machine Learning Fundamentals]]
- Distributed sensor data aggregation via [[MQTT Protocol]]
- Running simulation workloads for [[ESP32-S3 Robot Controller]]

Connects to [[Robotics Project Overview]] and uses patterns from [[Embedded Systems Design]].
