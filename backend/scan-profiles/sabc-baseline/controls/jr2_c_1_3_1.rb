control 'JR2.C.1.3.1' do
  title 'Ensure bootloader password is set.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_1_3_1'
  if os[:family] == 'debian'
    describe command(<<-'SABC_V'.chomp) do
      grep "^set superusers" /boot/grub/grub.cfg
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
  if os[:family] == 'redhat'
    describe command(<<-'SABC_V'.chomp) do
      grep -P '^\h*set\h+superusers' /boot/grub2/grub.cfg /boot/grub2/user.cfg 2>/dev/null
      grep -P '^\h*password' /boot/grub2/grub.cfg /boot/grub2/user.cfg 2>/dev/null
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
end
