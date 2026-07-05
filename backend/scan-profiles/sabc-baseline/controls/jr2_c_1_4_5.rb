control 'JR2.C.1.4.5' do
  title 'Ensure core dumps are restricted.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_1_4_5'
  if os[:family] == 'debian'
    describe command(<<-'SABC_V'.chomp) do
      grep -Es '^(\*|\s).*hard.*core.*(\s+#.*)?$' /etc/security/limits.conf /etc/security/limits.d/*
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
  if os[:family] == 'redhat'
    describe command(<<-'SABC_V'.chomp) do
      grep -Es '^(\*|\s).*hard.*core.*(\s+#.*)?$' /etc/security/limits.conf /etc/security/limits.d/*
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
end
