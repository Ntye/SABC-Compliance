control 'JR2.C.1.5.2' do
  title 'Ensure AppArmor is enabled in the bootloader configuration.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_1_5_2'
  if os.debian?
    v_debian = command(<<-'SABC_V'.chomp)
/bin/bash <<'SABC_BASH_EOF'
grep "^\s*linux" /boot/grub/grub.cfg | grep -v "apparmor=1"
SABC_BASH_EOF
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
/bin/bash <<'SABC_BASH_EOF'
#!/usr/bin/env bash
command -v grubby >/dev/null 2>&1 || exit 101
grubby --info=ALL 2>/dev/null | grep -Eq '(selinux=0|enforcing=0)' && exit 1
exit 0
SABC_BASH_EOF
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
