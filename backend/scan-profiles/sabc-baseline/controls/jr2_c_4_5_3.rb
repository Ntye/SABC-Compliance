control 'JR2.C.4.5.3' do
  title 'Ensure default user shell timeout is configured.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_4_5_3'
  if os.debian?
    v_debian = command(<<-'SABC_V'.chomp)
#!/bin/bash
v=$(grep -Ehs 'TMOUT=' /etc/profile.d/*.sh /etc/profile /etc/bash.bashrc 2>/dev/null | grep -oE 'TMOUT=[0-9]+' | tail -1 | cut -d= -f2)
[ -n "$v" ] && [ "$v" -ge 1 ] && [ "$v" -le 900 ] && exit 0
exit 1
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
t=$(grep -Ersho 'TMOUT=[0-9]+' /etc/profile /etc/profile.d /etc/bashrc 2>/dev/null | grep -Eo '[0-9]+' | tail -n1)
[ -n "$t" ] && [ "$t" -ge 1 ] && [ "$t" -le 900 ]
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
