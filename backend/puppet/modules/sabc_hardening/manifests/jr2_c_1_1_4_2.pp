# JR2.C.1.1.4.2 (CIS Level 1) — Ensure noexec option set on /var/tmp partition.
# Generated from the SABC referential. Enforcement is the family's own
# Configure procedure, run only when the Validate procedure fails.
class sabc_hardening::jr2_c_1_1_4_2 {
  if $facts['os']['family'] == 'Debian' {
    exec { 'sabc_jr2_c_1_1_4_2_debian':
      command  => @(SABC_CMD/L),
        <device> /var/tmp <fstype> defaults,rw,nosuid,nodev,noexec,relatime 0 0
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        findmnt -kn /var/tmp | grep -v 'noexec'
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
  if $facts['os']['family'] == 'RedHat' {
    exec { 'sabc_jr2_c_1_1_4_2_redhat':
      command  => @(SABC_CMD/L),
        <device> /var/tmp <fstype> defaults,rw,nosuid,nodev,noexec,relatime 0 0
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        findmnt -kn /var/tmp | grep -v 'noexec'
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
}
