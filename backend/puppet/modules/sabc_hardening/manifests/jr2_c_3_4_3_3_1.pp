# JR2.C.3.4.3.3.1 (CIS Level 1) — Ensure ip6tables default deny firewall policy.
# Generated from the SABC referential. Enforcement is the family's own
# Configure procedure, run only when the Validate procedure fails.
class sabc_hardening::jr2_c_3_4_3_3_1 {
  if $facts['os']['family'] == 'Debian' {
    exec { 'sabc_jr2_c_3_4_3_3_1_debian':
      command  => @(SABC_CMD/L),
        ip6tables -P INPUT DROP
        ip6tables -P OUTPUT DROP
        ip6tables -P FORWARD DROP
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        ip6tables -L -n
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
  if $facts['os']['family'] == 'RedHat' {
    exec { 'sabc_jr2_c_3_4_3_3_1_redhat':
      command  => @(SABC_CMD/L),
        ip6tables -P INPUT DROP
        ip6tables -P OUTPUT DROP
        ip6tables -P FORWARD DROP
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        ip6tables -L -n
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
}
