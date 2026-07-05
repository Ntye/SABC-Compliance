# JR2.C.1.1.6.3 (CIS Level 1) — Ensure nosuid option set on /var/log/audit partition.
# Generated from the SABC referential. Enforcement is the family's own
# Configure procedure, run only when the Validate procedure fails.
class sabc_hardening::jr2_c_1_1_6_3 {
  if $facts['os']['family'] == 'Debian' {
    exec { 'sabc_jr2_c_1_1_6_3_debian':
      command  => @(SABC_CMD/L),
        <device> /var/log/audit <fstype> defaults,rw,nosuid,nodev,noexec,relatime 0 0
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        findmnt -kn /var/log/audit | grep -v 'nosuid'
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
  if $facts['os']['family'] == 'RedHat' {
    exec { 'sabc_jr2_c_1_1_6_3_redhat':
      command  => @(SABC_CMD/L),
        <device> /var/log/audit <fstype> defaults,rw,nosuid,nodev,noexec,relatime 0 0
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        findmnt -kn /var/log/audit | grep -v 'nosuid'
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
}
