#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
systemctl stop httpd.socket httpd.service nginx.service 2>/dev/null || true
systemctl mask httpd.socket httpd.service nginx.service 2>/dev/null || true
dnf remove -y httpd nginx
