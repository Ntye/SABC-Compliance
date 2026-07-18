#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
systemctl is-active firewalld.service 2>/dev/null | grep -q '^active' && exit 0
nft list tables 2>/dev/null | grep -q . && exit 0
nft create table inet filter
