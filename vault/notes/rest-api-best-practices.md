---
title: REST API Best Practices
tags: [api, rest, web-development, backend]
---

# REST API Design Best Practices

Guidelines for building clean, maintainable REST APIs.

## Resource Naming

- Use nouns, not verbs: `/robots` not `/getRobots`
- Collection resources: `/robots` returns list
- Singular resources: `/robots/esp32-1` returns one

## HTTP Methods

- `GET` — retrieve resources
- `POST` — create resources
- `PUT` — update resources (full replacement)
- `PATCH` — partial update
- `DELETE` — remove resources

## Implementation

APIs built with **FastAPI** or **Flask** in Python, deployed via [[Docker Container Deployment]].

## Integration

Exposes robot status from [[ESP32-S3 Robot Controller]] and serves as the bridge between [[MQTT Protocol]] telemetry and web dashboards.

Related: [[Robotics Project Overview]], [[IoT Sensor Networks]].
