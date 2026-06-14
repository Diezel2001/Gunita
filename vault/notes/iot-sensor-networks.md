---
title: IoT Sensor Networks
tags: [iot, sensors, networking, data-collection]
---

# IoT Sensor Network Design

Architecture and implementation patterns for distributed sensor networks.

## Network Topology

- **Star** — central hub with leaf nodes (simplest)
- **Mesh** — nodes relay data through peers (most resilient)
- **Tree** — hierarchical aggregation (best for large deployments)

## Communication Protocols

- [[MQTT Protocol]] for lightweight publish-subscribe messaging
- CoAP for constrained RESTful environments
- LoRaWAN for long-range, low-power links

## Hardware

Nodes typically use **ESP32-S3** or similar microcontrollers with sensors for:
- Temperature and humidity
- Motion detection
- Air quality monitoring
- Ultrasonic ranging

These networks feed data into [[Machine Learning Fundamentals]] pipelines and connect to [[Robotics Project Overview]] systems.

## Power Management

- Deep sleep modes (ESP32: ~5 μA)
- Solar harvesting with battery backup
- Duty cycling for extended battery life
