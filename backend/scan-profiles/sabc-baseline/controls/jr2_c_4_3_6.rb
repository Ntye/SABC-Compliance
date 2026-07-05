control 'JR2.C.4.3.6' do
  title 'Ensure access to the su command is restricted.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_4_3_6'
  if os[:family] == 'debian'
    describe command(<<-'SABC_V'.chomp) do
      grep -Pi '^\h*auth\h+(?:required|requisite)\h+pam_wheel\.so\h+(?:[^#\n\r]+\h+)?((?!\2)(use_uid\b|group=\H+\b))\h+(?:[^#\n\r]+\h+)?((?!\1)(use_uid\b|group=\H+\b))(\h+.*)?$' /etc/pam.d/su
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
  if os[:family] == 'redhat'
    describe command(<<-'SABC_V'.chomp) do
      grep -Pi '^\h*auth\h+(?:required|requisite)\h+pam_wheel\.so\h+(?:[^#\n\r]+\h+)?((?!\2)(use_uid\b|group=\H+\b))\h+(?:[^#\n\r]+\h+)?((?!\1)(use_uid\b|group=\H+\b))(\h+.*)?$' /etc/pam.d/su
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
end
