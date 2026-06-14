---
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
