#!/usr/bin/env python3
"""Generate 15+ sample markdown notes in vault/notes/ for testing BFAI."""

import shutil
from pathlib import Path

NOTES_DIR = Path("vault/notes")
NOTES_DIR.mkdir(parents=True, exist_ok=True)

# Delete existing .md files
for f in list(NOTES_DIR.glob("*.md")):
    f.unlink()

notes = {}

notes["raspberry-pi-cluster"] = """---
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
"""

notes["embedded-systems-design"] = """---
title: Embedded Systems Design
tags: [embedded-systems, firmware, hardware, microcontrollers]
---

# Embedded Systems Design Patterns

Common design patterns for reliable embedded firmware development.

## Key Patterns

- **Super Loop** — simple polling architecture for bare-metal systems
- **RTOS Tasks** — preemptive multitasking with FreeRTOS
- **State Machines** — event-driven control flow using nested switch statements
- **Publisher-Subscriber** — loosely coupled component communication

## Hardware Considerations

When designing embedded systems like [[ESP32-S3 Robot Controller]], consider:
- Power consumption vs performance tradeoffs
- GPIO multiplexing limitations
- Peripheral DMA for efficient data transfer

## Firmware

Most projects use **MicroPython** or C with the ESP-IDF framework.
"""

notes["machine-learning-fundamentals"] = """---
title: Machine Learning Fundamentals
tags: [machine-learning, ai, python, data-science]
---

# Machine Learning Fundamentals

Core concepts in machine learning relevant to robotics and AI applications.

## Key Topics

- **Supervised Learning** — regression, classification, SVMs, neural networks
- **Unsupervised Learning** — clustering, dimensionality reduction
- **Reinforcement Learning** — Q-learning, policy gradients

## Libraries

Python ecosystem: **scikit-learn**, **TensorFlow**, **PyTorch**, **JAX**

## Applications in Robotics

- Computer vision object detection for [[ESP32-S3 Robot Controller]]
- Sensor fusion and state estimation
- Path planning and obstacle avoidance
- Natural language interfaces via [[Natural Language Processing]]

## Related Concepts

- Feature engineering and selection
- Model evaluation (cross-validation, confusion matrices)
- Deployment with [[Docker Container Deployment]]
"""

notes["natural-language-processing"] = """---
title: Natural Language Processing
tags: [nlp, ai, python, machine-learning]
---

# Natural Language Processing

Fundamentals of NLP for building conversational interfaces.

## Core Techniques

- Tokenization, stemming, lemmatization
- Word embeddings (Word2Vec, GloVe, BERT)
- Sequence models (RNNs, LSTMs, Transformers)
- Large Language Models (GPT, LLaMA)

## Applications

- Voice command interfaces for [[ESP32-S3 Robot Controller]]
- Document indexing and semantic search
- Knowledge base question answering

## Python Tools

- **spaCy** — industrial-strength NLP
- **NLTK** — educational toolkit
- **transformers** — Hugging Face ecosystem

Builds on [[Machine Learning Fundamentals]] and integrates with [[REST API Best Practices]] for serving models.
"""

notes["docker-container-deployment"] = """---
title: Docker Container Deployment
tags: [docker, devops, deployment, infrastructure]
---

# Docker Container Deployment

Using Docker for reproducible deployment of applications and services.

## Core Concepts

- Images and containers
- Dockerfiles and multi-stage builds
- Docker Compose for multi-service stacks
- Docker Swarm and Kubernetes for orchestration

## Usage in Projects

- Deploying [[MQTT Protocol]] brokers in containers
- Running [[Raspberry Pi Cluster]] services
- CI/CD pipelines for [[ESP32-S3 Robot Controller]] firmware
- Isolated environments for [[Machine Learning Fundamentals]] experiments

## Best Practices

- Keep images small (Alpine-based where possible)
- Use .dockerignore files
- Health checks and restart policies
- Secret management for API keys

See also [[REST API Best Practices]] for containerized API services.
"""

notes["rest-api-best-practices"] = """---
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
"""

notes["iot-sensor-networks"] = """---
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
"""

notes["micropython-firmware"] = """---
title: MicroPython Firmware
tags: [micropython, python, firmware, microcontrollers]
---

# MicroPython Firmware Guide

MicroPython is a lean implementation of Python 3 designed to run on microcontrollers.

## Supported Hardware

- ESP32 / [[ESP32-S3]]
- Raspberry Pi Pico (RP2040)
- STM32 family
- SAMD21/SAMD51

## Key Libraries

```python
from machine import Pin, ADC, PWM, I2C, SPI
import network      # Wi-Fi connectivity
import socket       # TCP/UDP networking
import ujson        # JSON parsing
import urequests    # HTTP requests
```

## Building Firmware

Custom firmware builds include:
- Compiled bytecode for speed-critical modules
- Frozen modules to save RAM
- Custom C extensions for hardware peripherals

Used extensively in [[ESP32-S3 Robot Controller]] and [[IoT Sensor Networks]].

## Development Workflow

1. Write code in MicroPython
2. Upload via USB serial or WebREPL
3. Debug with REPL and LED indicators
4. Deploy OTA updates via [[MQTT Protocol]]
"""

notes["linux-server-administration"] = """---
title: Linux Server Administration
tags: [linux, server, administration, devops]
---

# Linux Server Administration Guide

Essential Linux administration tasks for maintaining development and production servers.

## Common Tasks

- User and group management
- File permissions and ACLs
- Systemd service management
- Firewall configuration (iptables/nftables)
- Log management and rotation

## Container Hosting

Linux servers host [[Docker Container Deployment]] environments for:
- [[MQTT Protocol]] brokers
- [[REST API Best Practices]] services
- [[Machine Learning Fundamentals]] inference endpoints

## Monitoring

- Prometheus + Grafana for metrics
- ELK stack for log aggregation
- Netdata for real-time system monitoring

## Security

- SSH key-based authentication
- Fail2ban for intrusion prevention
- Regular security updates with unattended-upgrades
"""

notes["python-project-templates"] = """---
title: Python Project Templates
tags: [python, programming, development, templates]
---

# Python Project Templates

Standard project structures and templates for Python development.

## Recommended Structure

```
project/
├── src/
│   └── package/
│       ├── __init__.py
│       ├── module.py
│       └── ...
├── tests/
│   ├── __init__.py
│   └── test_module.py
├── pyproject.toml
├── README.md
└── USAGE_GUIDE.md
```

## Tools

- **Poetry** or **pip-tools** for dependency management
- **pytest** for testing (used by BFAI)
- **black** and **ruff** for formatting and linting
- **pre-commit** hooks for CI quality gates

## Deployment

Python packages deployed via [[Docker Container Deployment]] or as services following [[REST API Best Practices]].

## Related

- [[Machine Learning Fundamentals]] — ML project structure
- [[Embedded Systems Design]] — MicroPython projects on [[ESP32-S3]]
"""

notes["database-design-principles"] = """---
title: Database Design Principles
tags: [database, sql, design, architecture]
---

# Database Design Principles

Core principles for designing efficient and maintainable databases.

## Normalization

- **1NF** — Atomic values, no repeating groups
- **2NF** — No partial dependencies on composite keys
- **3NF** — No transitive dependencies

## SQLite

BFAI uses **SQLite** as its embedded database engine. Key advantages:
- Zero configuration required
- Single file storage
- FTS5 full-text search built-in
- ACID compliant with WAL mode

## Indexing Strategy

- Primary keys are auto-indexed
- Foreign keys should be indexed for JOIN performance
- Full-text search uses FTS5 virtual tables

## Related

- Database-backed [[REST API Best Practices]]
- [[IoT Sensor Networks]] time-series data storage
- [[Embedded Systems Design]] local storage patterns
"""

notes["project-management-tools"] = """---
title: Project Management Tools
tags: [project-management, tools, workflow, productivity]
---

# Project Management Tools and Workflows

Overview of tools and methodologies for managing technical projects.

## Version Control

- **Git** with feature branch workflow
- Conventional commits for changelog generation
- Code review via pull requests

## Issue Tracking

- GitHub Issues or Jira for task management
- Milestones for release planning
- Labels for categorization (bug, feature, enhancement)

## Documentation

- **Markdown** for all documentation (this vault!)
- README files for project overviews
- API docs generated from OpenAPI/Swagger specs

## CI/CD

Automated pipelines using [[Docker Container Deployment]]:
- Lint and test on every push
- Build and publish Docker images
- Deploy to staging/production

Related: [[Python Project Templates]] for project scaffolding.
"""

notes["web-development-fundamentals"] = """---
title: Web Development Fundamentals
tags: [web-development, javascript, css, html, frontend]
---

# Web Development Fundamentals

Core concepts for building modern web applications.

## Frontend Stack

- **HTML5** — semantic markup
- **CSS3** — Flexbox, Grid, responsive design
- **JavaScript/TypeScript** — interactive functionality
- **React**, **Vue**, or **Svelte** — component frameworks

## Backend Stack

- RESTful APIs following [[REST API Best Practices]]
- WebSocket servers for real-time communication
- Server-Sent Events for streaming data

## Real-Time Communication

The [[ESP32-S3 Robot Controller]] uses **WebSockets** for bidirectional control, similar to how web dashboards receive live updates.

## Deployment

Frontend apps packaged in [[Docker Container Deployment]] and served behind Nginx. Backend APIs follow [[REST API Best Practices]].

Related: [[IoT Sensor Networks]] for live data dashboards.
"""

notes["argocd-gitops"] = """---
title: ArgoCD and GitOps
tags: [gitops, argocd, kubernetes, devops]
---

# ArgoCD and GitOps Workflow

GitOps is an operational framework that uses Git as the single source of truth for infrastructure and application deployment.

## Core Principles

- The **desired state** is declared in a Git repository
- An operator (ArgoCD) **reconciles** actual state to match
- All changes go through **pull requests**

## Benefits

- Full audit trail of infrastructure changes
- Easy rollback by reverting Git commits
- Disaster recovery from Git history

## Integration

- Deploys [[Docker Container Deployment]] images to Kubernetes
- Works with [[Raspberry Pi Cluster]] for edge Kubernetes
- Supports [[REST API Best Practices]] services

## Related

- [[Linux Server Administration]] for cluster management
- [[Project Management Tools]] for workflow integration
"""

notes["computer-vision-robotics"] = """---
title: Computer Vision for Robotics
tags: [computer-vision, robotics, ai, python]
---

# Computer Vision for Robotics

Applying computer vision techniques to robotic systems.

## Core Techniques

- **Camera Calibration** — intrinsic/extrinsic parameters
- **Feature Detection** — SIFT, ORB, FAST corner detection
- **Object Detection** — YOLO, SSD, Faster R-CNN
- **Visual SLAM** — ORB-SLAM3, RTAB-Map

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
"""

notes["data-visualization"] = """---
title: Data Visualization
tags: [data-visualization, python, analytics, dashboards]
---

# Data Visualization Techniques

Effective ways to visualize data for analysis and presentation.

## Python Libraries

- **Matplotlib** — comprehensive plotting library
- **Seaborn** — statistical data visualization
- **Plotly** — interactive web-based charts
- **Dash** — web dashboards built on Plotly

## Visualization Types

- Time series plots for [[IoT Sensor Networks]] data
- Correlation heatmaps for [[Machine Learning Fundamentals]]
- Network graphs for knowledge relationships
- Real-time dashboards for [[ESP32-S3 Robot Controller]]

## Dashboard Architecture

Dashboards consume data from [[REST API Best Practices]] endpoints and stream from [[MQTT Protocol]] topics, deployed via [[Docker Container Deployment]].

## Best Practices

- Choose the right chart type for the data
- Use color effectively and consistently
- Include interactive tooltips for exploration
"""

# Write all notes
for filename, content in notes.items():
    path = NOTES_DIR / f"{filename}.md"
    path.write_text(content.strip() + "\n")
    print(f"  ✓ {filename}.md")

print(f"\n✅ Generated {len(notes)} sample notes in {NOTES_DIR}")