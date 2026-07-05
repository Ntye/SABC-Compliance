# JR2.C.1.3.2 (CIS Level 1) — Ensure permissions on bootloader config are configured.
# Generated from the SABC referential. Enforcement is the family's own
# Configure procedure, run only when the Validate procedure fails.
class sabc_hardening::jr2_c_1_3_2 {
  if $facts['os']['family'] == 'Debian' {
    exec { 'sabc_jr2_c_1_3_2_debian':
      command  => @(SABC_CMD/L),
        chown root:root /boot/grub/grub.cfg
        chmod u-x,go-rwx /boot/grub/grub.cfg
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        stat -Lc 'Access: (%#a/%A) Uid: ( %u/ %U) Gid: ( %g/ %G)' /boot/grub/grub.cfg
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
  if $facts['os']['family'] == 'RedHat' {
    exec { 'sabc_jr2_c_1_3_2_redhat':
      command  => @(SABC_CMD/L),
        chown root:root /boot/grub2/grub.cfg
        chmod 0600 /boot/grub2/grub.cfg
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        stat -Lc 'Access: (%#a/%A) Uid: (%u/%U) Gid: (%g/%G)' /boot/grub2/grub.cfg
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
}
