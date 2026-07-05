control 'JR2.C.3.4.1.6' do
  title 'Ensure ufw default deny firewall policy.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_3_4_1_6'
  if os[:family] == 'debian'
    describe command(<<-'SABC_V'.chomp) do
      ufw status verbose | grep Default:
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
  if os[:family] == 'redhat'
    describe command(<<-'SABC_V'.chomp) do
      firewall-cmd --get-default-zone
      firewall-cmd --permanent --zone=$(firewall-cmd --get-default-zone) --get-target
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
end
