# JR2.C.1.3.1 (CIS Level 1) — Ensure bootloader password is set.
# Generated from the SABC referential. Enforcement is the family's own
# Configure procedure, run only when the Validate procedure fails.
class sabc_hardening::jr2_c_1_3_1 {
  if $facts['os']['family'] == 'Debian' {
    exec { 'sabc_jr2_c_1_3_1_debian':
      command  => @(SABC_CMD/L),
        grub-mkpasswd-pbkdf2
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        grep "^set superusers" /boot/grub/grub.cfg
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
  if $facts['os']['family'] == 'RedHat' {
    exec { 'sabc_jr2_c_1_3_1_redhat':
      command  => @(SABC_CMD/L),
        grub2-setpassword
        grub2-mkconfig -o /boot/grub2/grub.cfg   # BIOS
        grub2-mkconfig -o /boot/efi/EFI/redhat/grub.cfg   # UEFI
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        grep -P '^\h*set\h+superusers' /boot/grub2/grub.cfg /boot/grub2/user.cfg 2>/dev/null
        grep -P '^\h*password' /boot/grub2/grub.cfg /boot/grub2/user.cfg 2>/dev/null
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
}
