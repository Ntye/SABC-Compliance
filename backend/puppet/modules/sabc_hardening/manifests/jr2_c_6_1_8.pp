# JR2.C.6.1.8 (CIS Level 1) — Ensure permissions on /etc/gshadow- are configured.
# Generated from the SABC referential. Enforcement is the family's own
# Configure procedure, run only when the Validate procedure fails.
class sabc_hardening::jr2_c_6_1_8 {
  if $facts['os']['family'] == 'Debian' {
    exec { 'sabc_jr2_c_6_1_8_debian':
      command  => @(SABC_CMD/L),
        chown root:shadow /etc/gshadow-
        chown root:root /etc/gshadow-
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        stat -Lc "%n %a %u/%U %g/%G" /etc/gshadow-
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
  if $facts['os']['family'] == 'RedHat' {
    exec { 'sabc_jr2_c_6_1_8_redhat':
      command  => @(SABC_CMD/L),
        chown root:shadow /etc/gshadow-
        chown root:root /etc/gshadow-
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        stat -Lc "%n %a %u/%U %g/%G" /etc/gshadow-
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
}
