# JR2.C.1.1.2.1 (CIS Level 1) — Ensure /tmp is a separate partition.
# Generated from the SABC referential. Enforcement is the family's own
# Configure procedure, run only when the Validate procedure fails.
class sabc_hardening::jr2_c_1_1_2_1 {
  if $facts['os']['family'] == 'Debian' {
    exec { 'sabc_jr2_c_1_1_2_1_debian':
      command  => @(SABC_CMD/L),
        tmpfs /tmp tmpfs defaults,rw,nosuid,nodev,noexec,relatime 0 0
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        findmnt -nk /tmp
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
  if $facts['os']['family'] == 'RedHat' {
    exec { 'sabc_jr2_c_1_1_2_1_redhat':
      command  => @(SABC_CMD/L),
        tmpfs /tmp tmpfs defaults,rw,nosuid,nodev,noexec,relatime 0 0
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        findmnt -nk /tmp
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
}
