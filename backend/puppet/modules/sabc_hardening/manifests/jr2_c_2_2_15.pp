# JR2.C.2.2.15 (CIS Level 1) — Ensure mail transfer agent is configured for local-only mode.
# Generated from the SABC referential. Enforcement is the family's own
# Configure procedure, run only when the Validate procedure fails.
class sabc_hardening::jr2_c_2_2_15 {
  if $facts['os']['family'] == 'Debian' {
    exec { 'sabc_jr2_c_2_2_15_debian':
      command  => @(SABC_CMD/L),
        inet_interfaces = loopback-only
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        ss -lntu | grep -P ':25\b' | grep -Pv '\h+(127\.0\.0\.1|\[?::1\]?):25\b'
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
  if $facts['os']['family'] == 'RedHat' {
    exec { 'sabc_jr2_c_2_2_15_redhat':
      command  => @(SABC_CMD/L),
        inet_interfaces = loopback-only
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        ss -lntu | grep -P ':25\b' | grep -Pv '\h+(127\.0\.0\.1|\[?::1\]?):25\b'
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
}
