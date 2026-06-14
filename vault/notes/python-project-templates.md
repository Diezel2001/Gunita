---
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
