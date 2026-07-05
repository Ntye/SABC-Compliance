# JR2.C.1.1.7.2 (CIS Level 1) — Ensure nosuid option set on /home partition.
# Generated from the SABC referential. Enforcement is the family's own
# Configure procedure, run only when the Validate procedure fails.
class sabc_hardening::jr2_c_1_1_7_2 {
  if $facts['os']['family'] == 'Debian' {
    exec { 'sabc_jr2_c_1_1_7_2_debian':
      command  => @(SABC_CMD/L),
        <device> /home <fstype> defaults,rw,nosuid,nodev,relatime 0 0
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        findmnt -kn /home | grep -v 'nosuid'
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
  if $facts['os']['family'] == 'RedHat' {
    exec { 'sabc_jr2_c_1_1_7_2_redhat':
      command  => @(SABC_CMD/L),
        <device> /home <fstype> defaults,rw,nosuid,nodev,relatime 0 0
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        findmnt -kn /home | grep -v 'nosuid'
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
}
