---
id: KONG-INC-001
type: incident
title: 'Kong 504: upstream slower than the service read timeout'
platform: kong
category: TIMEOUT
secondary_categories: []
severity: P3
versions:
- '3.6'
- '3.8'
os:
- container
components:
- kong-dp
- orders-svc
signatures:
- 'upstream timed out (110: Connection timed out) while reading response header from upstream'
- '504'
root_causes:
- kong_upstream_timeout
runbooks: []
verified: true
---

# KONG-INC-001 Kong 504: upstream slower than the service read timeout

## Symptoms

Partner calls to one route return 504 from Kong; error.log shows upstream timed out while reading response header.

## Root cause

The orders service slowed after a database change; its responses took longer than the Kong service read_timeout.

## Resolution steps

1. [read] Check upstream latency for the route in access.log.
2. [read] Read the service timeouts with Admin API GET /services/{name}.
3. [read] Check the orders service health and its own logs.
4. [change] Fix the backend slowness; raise read_timeout only with the backend owner's approval.

## Verification

No 504s on the route; upstream latency under the timeout.
