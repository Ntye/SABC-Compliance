# JR2.C.3.4.3.3.3 (CIS Level 1) — Ensure ip6tables firewall rules exist for all open ports.
# Generated from the SABC referential. Enforcement is the family's own
# Configure procedure, run only when the Validate procedure fails.
class sabc_hardening::jr2_c_3_4_3_3_3 {
  if $facts['os']['family'] == 'Debian' {
    exec { 'sabc_jr2_c_3_4_3_3_3_debian':
      command  => @(SABC_CMD/L),
        ip6tables -A INPUT -p <protocol> --dport <port> -m state --state NEW -j ACCEPT
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        ss -6tuln
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
  if $facts['os']['family'] == 'RedHat' {
    exec { 'sabc_jr2_c_3_4_3_3_3_redhat':
      command  => @(SABC_CMD/L),
        ip6tables -A INPUT -p <protocol> --dport <port> -m state --state NEW -j ACCEPT
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        ss -6tuln
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
}
