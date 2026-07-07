control 'JR2.C.1.6.1' do
  title 'Ensure message of the day is configured properly.'
  impact 0.7
  tag cis_level: 2
  tag control_key: 'jr2_c_1_6_1'
  if os[:family] == 'debian'
    v_debian = command(<<-'SABC_V'.chomp)
      #!/bin/bash
      [ -e /etc/motd ] || exit 0
      os_id=$(grep '^ID=' /etc/os-release | cut -d= -f2 | tr -d '"')
      grep -Eqis "(\\\\v|\\\\r|\\\\m|\\\\s|$os_id)" /etc/motd && exit 1
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
  if os[:family] == 'redhat'
    v_redhat = command(<<-'SABC_V'.chomp)
      #!/bin/bash
      [ -e /etc/motd ] || exit 0
      os_id=$(grep '^ID=' /etc/os-release | cut -d= -f2 | tr -d '"')
      grep -Eqis "(\\\\v|\\\\r|\\\\m|\\\\s|$os_id)" /etc/motd && exit 1
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
