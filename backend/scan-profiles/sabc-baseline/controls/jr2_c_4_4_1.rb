control 'JR2.C.4.4.1' do
  title 'Ensure password creation requirements are configured.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_4_4_1'
  if os.debian?
    v_debian = command(<<-'SABC_V'.chomp)
/bin/bash <<'SABC_BASH_EOF'
#!/bin/bash
dpkg-query -W libpam-pwquality >/dev/null 2>&1 || exit 1
v=$(grep -Ehs '^[[:space:]]*minlen[[:space:]]*=' /etc/security/pwquality.conf /etc/security/pwquality.conf.d/*.conf 2>/dev/null | tail -1 | grep -oE '[0-9]+')
[ -n "$v" ] && [ "$v" -ge 14 ] || exit 1
c=$(grep -Ehs '^[[:space:]]*minclass[[:space:]]*=' /etc/security/pwquality.conf /etc/security/pwquality.conf.d/*.conf 2>/dev/null | tail -1 | grep -oE '[0-9]+')
[ -n "$c" ] && [ "$c" -ge 4 ] || exit 1
exit 0
SABC_BASH_EOF
    SABC_V
    if v_debian.exit_status == 101
      describe 'Not applicable' do
        skip 'Not applicable on this node: the validate procedure reported its prerequisite (package/service) is absent.'
      end
    else
      describe v_debian do
        its('exit_status') { should cmp 0 }
      end
    end
  end
  if os.redhat?
    v_redhat = command(<<-'SABC_V'.chomp)
/bin/bash <<'SABC_BASH_EOF'
#!/usr/bin/env bash
rpm -q libpwquality >/dev/null 2>&1 || exit 1
conf() { awk -F= -v k="$1" '$1 ~ "^\\s*"k"\\s*$" {gsub(/ /,"",$2); v=$2} END {print v}' \
  /etc/security/pwquality.conf /etc/security/pwquality.conf.d/*.conf 2>/dev/null; }
ml=$(conf minlen); [ -n "$ml" ] && [ "$ml" -ge 14 ] || exit 1
mc=$(conf minclass)
if [ -n "$mc" ]; then [ "$mc" -ge 4 ] || exit 1
else
  for k in dcredit ucredit lcredit ocredit; do
    cv=$(conf $k); [ -n "$cv" ] && [ "$cv" -le -1 ] || exit 1
  done
fi
grep -Eq 'pam_pwquality\.so' /etc/pam.d/system-auth /etc/pam.d/password-auth || exit 1
exit 0
SABC_BASH_EOF
    SABC_V
    if v_redhat.exit_status == 101
      describe 'Not applicable' do
        skip 'Not applicable on this node: the validate procedure reported its prerequisite (package/service) is absent.'
      end
    else
      describe v_redhat do
        its('exit_status') { should cmp 0 }
      end
    end
  end
end
