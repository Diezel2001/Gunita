---
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
