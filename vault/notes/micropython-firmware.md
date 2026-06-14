---
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
