# JR2.C.4.1.1 (CIS Level 1) — Ensure cron daemon is enabled and active.
# Generated from the SABC referential. Enforcement is the family's own
# Configure procedure, run only when the Validate procedure fails.
class sabc_hardening::jr2_c_4_1_1 {
  if $facts['os']['family'] == 'Debian' {
    exec { 'sabc_jr2_c_4_1_1_debian':
      command  => @(SABC_CMD/L),
        systemctl unmask cron
        systemctl --now enable cron
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        systemctl is-enabled cron
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
  if $facts['os']['family'] == 'RedHat' {
    exec { 'sabc_jr2_c_4_1_1_redhat':
      command  => @(SABC_CMD/L),
        systemctl unmask cron
        systemctl --now enable cron
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        systemctl is-enabled cron
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
}
