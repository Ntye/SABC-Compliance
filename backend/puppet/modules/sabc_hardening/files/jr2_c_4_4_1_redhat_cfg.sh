#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true

{
   for l_pam_file in system-auth password-auth; do
     l_authselect_file="/etc/authselect/$(head -1
/etc/authselect/authselect.conf | grep 'custom/')/$l_pam_file"
     sed -ri
's/(^\s*password\s+(requisite|required|sufficient)\s+pam_pwquality\.so.*)(\s+
minclass\s*=\s*\S+)(.*$)/\1\4/' "$l_authselect_file"
     sed -ri
's/(^\s*password\s+(requisite|required|sufficient)\s+pam_pwquality\.so.*)(\s+
dcredit\s*=\s*\S+)(.*$)/\1\4/' "$l_authselect_file"
     sed -ri
's/(^\s*password\s+(requisite|required|sufficient)\s+pam_pwquality\.so.*)(\s+
ucredit\s*=\s*\S+)(.*$)/\1\4/' "$l_authselect_file"
     sed -ri
's/(^\s*password\s+(requisite|required|sufficient)\s+pam_pwquality\.so.*)(\s+
lcredit\s*=\s*\S+)(.*$)/\1\4/' "$l_authselect_file"
     sed -ri
's/(^\s*password\s+(requisite|required|sufficient)\s+pam_pwquality\.so.*)(\s+
ocredit\s*=\s*\S+)(.*$)/\1\4/' "$l_authselect_file"
   done
   authselect apply-changes
}
