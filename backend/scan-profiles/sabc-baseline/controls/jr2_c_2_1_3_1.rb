control 'JR2.C.2.1.3.1' do
  title 'Ensure systemd-timesyncd configured with authorized timeserver.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_2_1_3_1'
  if os.debian?
    v_debian = command(<<-'SABC_V'.chomp)
      #!/bin/bash
      systemctl is-enabled systemd-timesyncd 2>/dev/null | grep -q '^enabled' || exit 101
      grep -Ersq '^[[:space:]]*(NTP|FallbackNTP)=[^[:space:]]' /etc/systemd/timesyncd.conf /etc/systemd/timesyncd.conf.d 2>/dev/null && exit 0
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
      #!/bin/bash
      systemctl is-enabled systemd-timesyncd 2>/dev/null | grep -q '^enabled' || exit 101
      grep -Ersq '^[[:space:]]*(NTP|FallbackNTP)=[^[:space:]]' /etc/systemd/timesyncd.conf /etc/systemd/timesyncd.conf.d 2>/dev/null && exit 0
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
