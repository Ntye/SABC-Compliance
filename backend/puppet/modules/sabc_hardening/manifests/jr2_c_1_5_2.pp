# JR2.C.1.5.2 (CIS Level 1) — Ensure AppArmor is enabled in the bootloader configuration.
# Generated from the SABC referential. Enforcement is the family's own
# Configure procedure, run only when the Validate procedure fails.
class sabc_hardening::jr2_c_1_5_2 {
  if $facts['os']['family'] == 'Debian' {
    exec { 'sabc_jr2_c_1_5_2_debian':
      command  => @(SABC_CMD/L),
        GRUB_CMDLINE_LINUX="apparmor=1 security=apparmor"
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        grep "^\s*linux" /boot/grub/grub.cfg | grep -v "apparmor=1"
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
  if $facts['os']['family'] == 'RedHat' {
    exec { 'sabc_jr2_c_1_5_2_redhat':
      command  => @(SABC_CMD/L),
        sed -ri 's/(selinux|enforcing)=0\s*//g' /etc/default/grub
        grub2-mkconfig -o /boot/grub2/grub.cfg
        sed -ri 's/^SELINUX=.*/SELINUX=enforcing/' /etc/selinux/config
        setenforce 1
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        grep -P '^\h*(GRUB_CMDLINE_LINUX(_DEFAULT)?=.*)(selinux=0|enforcing=0)' /etc/default/grub
        grep -P '^\h*SELINUX=' /etc/selinux/config
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
}
