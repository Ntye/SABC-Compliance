control 'JR2.C.3.3.4' do
  title 'Ensure suspicious packets are logged.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_3_3_4'
  if os.debian?
    v_debian = command(<<-'SABC_V'.chomp)
#!/bin/bash
[ "$(sysctl -n net.ipv4.conf.all.log_martians 2>/dev/null)" = "1" ] || exit 1
[ "$(sysctl -n net.ipv4.conf.default.log_martians 2>/dev/null)" = "1" ] || exit 1
grep -Ersq '^[[:space:]]*net\.ipv4\.conf\.all\.log_martians[[:space:]]*=[[:space:]]*1' /etc/sysctl.conf /etc/sysctl.d 2>/dev/null || exit 1
grep -Ersq '^[[:space:]]*net\.ipv4\.conf\.default\.log_martians[[:space:]]*=[[:space:]]*1' /etc/sysctl.conf /etc/sysctl.d 2>/dev/null || exit 1
exit 0
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
#!/usr/bin/env bash
[ "$(sysctl -n net.ipv4.conf.all.log_martians 2>/dev/null)" = "1" ] || exit 1
[ "$(sysctl -n net.ipv4.conf.default.log_martians 2>/dev/null)" = "1" ] || exit 1
exit 0
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
