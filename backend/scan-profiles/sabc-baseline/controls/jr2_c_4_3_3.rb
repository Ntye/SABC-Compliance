control 'JR2.C.4.3.3' do
  title 'Ensure sudo log file exists.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_4_3_3'
  if os[:family] == 'debian'
    describe command(<<-'SABC_V'.chomp) do
      grep -rPsi "^\h*Defaults\h+([^#]+,\h*)?logfile\h*=\h*(\"|\')?\H+(\"|\')?(,\h*\H+\h*)*\h*(#.*)?$" /etc/sudoers*
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
  if os[:family] == 'redhat'
    describe command(<<-'SABC_V'.chomp) do
      grep -rPsi "^\h*Defaults\h+([^#]+,\h*)?logfile\h*=\h*(\"|\')?\H+(\"|\')?(,\h*\H+\h*)*\h*(#.*)?$" /etc/sudoers*
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
end
