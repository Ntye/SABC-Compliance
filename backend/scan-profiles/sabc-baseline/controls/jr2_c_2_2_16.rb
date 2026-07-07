control 'JR2.C.2.2.16' do
  title 'Ensure rsync service is either not installed or is masked.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_2_2_16'
  if os[:family] == 'debian'
    v_debian = command(<<-'SABC_V'.chomp)
      #!/bin/bash
      dpkg-query -W rsync >/dev/null 2>&1 || exit 0
      systemctl list-unit-files 2>/dev/null | grep -q '^rsync\.service' || exit 0
      [ "$(systemctl is-enabled rsync 2>/dev/null)" = "masked" ] && exit 0
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
  if os[:family] == 'redhat'
    v_redhat = command(<<-'SABC_V'.chomp)
      #!/bin/bash
      rpm -q rsync-daemon >/dev/null 2>&1 || rpm -q rsync >/dev/null 2>&1 || exit 0
      systemctl list-unit-files 2>/dev/null | grep -q '^rsyncd\.service' || exit 0
      [ "$(systemctl is-enabled rsyncd 2>/dev/null)" = "masked" ] && exit 0
      exit 1
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
