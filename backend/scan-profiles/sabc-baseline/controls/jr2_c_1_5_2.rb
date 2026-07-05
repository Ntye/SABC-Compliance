control 'JR2.C.1.5.2' do
  title 'Ensure AppArmor is enabled in the bootloader configuration.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_1_5_2'
  if os[:family] == 'debian'
    describe command(<<-'SABC_V'.chomp) do
      grep "^\s*linux" /boot/grub/grub.cfg | grep -v "apparmor=1"
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
  if os[:family] == 'redhat'
    describe command(<<-'SABC_V'.chomp) do
      grep -P '^\h*(GRUB_CMDLINE_LINUX(_DEFAULT)?=.*)(selinux=0|enforcing=0)' /etc/default/grub
      grep -P '^\h*SELINUX=' /etc/selinux/config
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
end
