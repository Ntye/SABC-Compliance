control 'JR2.C.1.3.2' do
  title 'Ensure permissions on bootloader config are configured.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_1_3_2'
  if os[:family] == 'debian'
    describe command(<<-'SABC_V'.chomp) do
      stat -Lc 'Access: (%#a/%A) Uid: ( %u/ %U) Gid: ( %g/ %G)' /boot/grub/grub.cfg
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
  if os[:family] == 'redhat'
    describe command(<<-'SABC_V'.chomp) do
      stat -Lc 'Access: (%#a/%A) Uid: (%u/%U) Gid: (%g/%G)' /boot/grub2/grub.cfg
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
end
