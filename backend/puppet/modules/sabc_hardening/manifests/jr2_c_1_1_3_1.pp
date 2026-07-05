# JR2.C.1.1.3.1 (CIS Level 1) — Ensure nodev option set on /var partition.
# Generated from the SABC referential. Enforcement is the family's own
# Configure procedure, run only when the Validate procedure fails.
class sabc_hardening::jr2_c_1_1_3_1 {
  if $facts['os']['family'] == 'Debian' {
    exec { 'sabc_jr2_c_1_1_3_1_debian':
      command  => @(SABC_CMD/L),
        <device> /var <fstype> defaults,rw,nosuid,nodev,relatime 0 0
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        findmnt -kn /var | grep -v 'nodev'
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
  if $facts['os']['family'] == 'RedHat' {
    exec { 'sabc_jr2_c_1_1_3_1_redhat':
      command  => @(SABC_CMD/L),
        <device> /var <fstype> defaults,rw,nosuid,nodev,relatime 0 0
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        findmnt -kn /var | grep -v 'nodev'
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
}
