# JR2.C.1.4.5 (CIS Level 1) — Ensure core dumps are restricted.
# Generated from the SABC referential. Enforcement is the family's own
# Configure procedure, run only when the Validate procedure fails.
class sabc_hardening::jr2_c_1_4_5 {
  if $facts['os']['family'] == 'Debian' {
    exec { 'sabc_jr2_c_1_4_5_debian':
      command  => @(SABC_CMD/L),
        * hard core 0
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        grep -Es '^(\*|\s).*hard.*core.*(\s+#.*)?$' /etc/security/limits.conf /etc/security/limits.d/*
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
  if $facts['os']['family'] == 'RedHat' {
    exec { 'sabc_jr2_c_1_4_5_redhat':
      command  => @(SABC_CMD/L),
        * hard core 0
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        grep -Es '^(\*|\s).*hard.*core.*(\s+#.*)?$' /etc/security/limits.conf /etc/security/limits.d/*
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
}
