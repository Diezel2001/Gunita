---
title: ArgoCD and GitOps
tags: [gitops, argocd, kubernetes, devops]
---

# ArgoCD and GitOps Workflow

GitOps is an operational framework that uses Git as the single source of truth for infrastructure and application deployment.

## Core Principles

- The **desired state** is declared in a Git repository
- An operator (ArgoCD) **reconciles** actual state to match
- All changes go through **pull requests**
s

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
