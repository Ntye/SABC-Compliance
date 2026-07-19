control 'JR2.C.5.1.2.4' do
  title 'Ensure rsyslog is not configured to receive logs from a remote client.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_5_1_2_4'
  if os.debian?
    v_debian = command(<<-'SABC_V'.chomp)
/bin/bash <<'SABC_BASH_EOF'
#!/bin/bash
grep -Ehs '^[[:space:]]*(module\(load="im(tcp|udp)"\)|input\(type="im(tcp|udp)"|\$ModLoad[[:space:]]+im(tcp|udp)|\$(InputTCPServerRun|UDPServerRun))' /etc/rsyslog.conf /etc/rsyslog.d/*.conf 2>/dev/null | grep -q . && exit 1
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
rpm -q rsyslog >/dev/null 2>&1 || exit 101
grep -Ersq '^\s*(module\(load="imtcp"\)|module\(load="imudp"\)|\$ModLoad\s+(imtcp|imudp))' /etc/rsyslog.conf /etc/rsyslog.d 2>/dev/null && exit 1
grep -Ersq '^\s*(input\(type="imtcp"|input\(type="imudp"|\$(InputTCPServerRun|UDPServerRun))' /etc/rsyslog.conf /etc/rsyslog.d 2>/dev/null && exit 1
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
