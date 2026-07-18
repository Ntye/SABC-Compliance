control 'JR2.C.1.3.1' do
  title 'Ensure bootloader password is set.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_1_3_1'
  if os.debian?
    v_debian = command(<<-'SABC_V'.chomp)
grep "^set superusers" /boot/grub/grub.cfg
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
#!/usr/bin/env bash
for f in /boot/grub2/user.cfg /boot/efi/EFI/*/user.cfg; do
  [ -f "$f" ] && grep -q '^GRUB2_PASSWORD=grub\.pbkdf2' "$f" && exit 0
done
exit 1
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
