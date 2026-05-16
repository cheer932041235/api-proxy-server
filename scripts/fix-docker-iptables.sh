#!/bin/bash
# fix-docker-iptables.sh — Fix Docker FORWARD chain after daemon restart
# Install as systemd service: see install instructions below

set -e

echo "[$(date)] Fixing Docker iptables FORWARD rules..."

# Wait for Docker to be ready
sleep 5

# Add FORWARD rules for docker0
iptables -I FORWARD 2 -o docker0 -j DOCKER 2>/dev/null || true
iptables -I FORWARD 2 -o docker0 -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT 2>/dev/null || true
iptables -I FORWARD 2 -i docker0 ! -o docker0 -j ACCEPT 2>/dev/null || true
iptables -I FORWARD 2 -i docker0 -o docker0 -j ACCEPT 2>/dev/null || true

echo "[$(date)] Docker iptables FORWARD rules fixed."
