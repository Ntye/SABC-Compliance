control 'JR2.C.4.5.1' do
  title 'Ensure default group for the root account is GID 0.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_4_5_1'
  if os[:family] == 'debian'
    describe command(<<-'SABC_V'.chomp) do
      grep "^root:" /etc/passwd | cut -f4 -d:
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
  if os[:family] == 'redhat'
    describe command(<<-'SABC_V'.chomp) do
      grep "^root:" /etc/passwd | cut -f4 -d:
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
end
