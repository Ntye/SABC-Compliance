# JR2.C.5.1.1.3 (CIS Level 1) — Ensure journald is configured to write logfiles to persistent disk.
# Generated from the SABC referential. Enforcement is the family's own
# Configure procedure, run only when the Validate procedure fails.
class sabc_hardening::jr2_c_5_1_1_3 {
  if $facts['os']['family'] == 'Debian' {
    exec { 'sabc_jr2_c_5_1_1_3_debian':
      command  => @(SABC_CMD/L),
        Storage=persistent
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        grep -Psi '^\h*Storage\h*=\h*persistent\b' /etc/systemd/journald.conf /etc/systemd/journald.conf.d/*
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
  if $facts['os']['family'] == 'RedHat' {
    exec { 'sabc_jr2_c_5_1_1_3_redhat':
      command  => @(SABC_CMD/L),
        Storage=persistent
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        grep -Psi '^\h*Storage\h*=\h*persistent\b' /etc/systemd/journald.conf /etc/systemd/journald.conf.d/*
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
}
