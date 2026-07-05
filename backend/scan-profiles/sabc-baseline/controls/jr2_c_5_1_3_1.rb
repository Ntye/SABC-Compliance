control 'JR2.C.5.1.3.1' do
  title 'Ensure cryptographic mechanisms are used to protect the integrity of audit tools.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_5_1_3_1'
  if os[:family] == 'debian'
    describe command(<<-'SABC_V'.chomp) do
      grep -Ps -- '(\/sbin\/(audit|au)\H*\b)' /etc/aide.conf /etc/aide/aide.conf /etc/aide.conf.d/*.conf /etc/aide/aide.conf.d/*
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
  if os[:family] == 'redhat'
    describe command(<<-'SABC_V'.chomp) do
      grep -Ps -- '(\/sbin\/(audit|au)\H*\b)' /etc/aide.conf /etc/aide/aide.conf /etc/aide.conf.d/*.conf /etc/aide/aide.conf.d/*
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
end
