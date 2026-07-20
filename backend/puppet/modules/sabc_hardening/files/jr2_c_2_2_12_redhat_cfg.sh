#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
systemctl stop snmpd.service 2>/dev/null || true
systemctl mask snmpd.service 2>/dev/null || true
dnf remove -y net-snmp
