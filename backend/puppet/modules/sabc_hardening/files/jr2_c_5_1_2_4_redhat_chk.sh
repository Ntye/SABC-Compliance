#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
rpm -q rsyslog >/dev/null 2>&1 || exit 101
grep -Ersq '^\s*(module\(load="imtcp"\)|module\(load="imudp"\)|\$ModLoad\s+(imtcp|imudp))' /etc/rsyslog.conf /etc/rsyslog.d 2>/dev/null && exit 1
grep -Ersq '^\s*(input\(type="imtcp"|input\(type="imudp"|\$(InputTCPServerRun|UDPServerRun))' /etc/rsyslog.conf /etc/rsyslog.d 2>/dev/null && exit 1
exit 0
