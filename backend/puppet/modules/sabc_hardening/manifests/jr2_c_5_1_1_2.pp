# JR2.C.5.1.1.2 (CIS Level 1) — Ensure journald is configured to compress large log files.
# Generated from the SABC referential. Enforcement is the family's own
# Configure procedure, run only when the Validate procedure fails.
class sabc_hardening::jr2_c_5_1_1_2 {
  if $facts['os']['family'] == 'Debian' {
    exec { 'sabc_jr2_c_5_1_1_2_debian':
      command  => @(SABC_CMD/L),
        Compress=yes
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        grep -Psi '^\h*Compress\h*=\h*yes\b' /etc/systemd/journald.conf /etc/systemd/journald.conf.d/*
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
  if $facts['os']['family'] == 'RedHat' {
    exec { 'sabc_jr2_c_5_1_1_2_redhat':
      command  => @(SABC_CMD/L),
        Compress=yes
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        grep -Psi '^\h*Compress\h*=\h*yes\b' /etc/systemd/journald.conf /etc/systemd/journald.conf.d/*
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
}
