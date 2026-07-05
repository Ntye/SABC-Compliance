# JR2.C.3.4.3.3.2 (CIS Level 1) — Ensure ip6tables loopback traffic is configured.
# Generated from the SABC referential. Enforcement is the family's own
# Configure procedure, run only when the Validate procedure fails.
class sabc_hardening::jr2_c_3_4_3_3_2 {
  if $facts['os']['family'] == 'Debian' {
    exec { 'sabc_jr2_c_3_4_3_3_2_debian':
      command  => @(SABC_CMD/L),
        ip6tables -A INPUT -i lo -j ACCEPT
        ip6tables -A OUTPUT -o lo -j ACCEPT
        ip6tables -A INPUT -s ::1 -j DROP
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        ip6tables -L INPUT -v -n
        ip6tables -L OUTPUT -v -n
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
  if $facts['os']['family'] == 'RedHat' {
    exec { 'sabc_jr2_c_3_4_3_3_2_redhat':
      command  => @(SABC_CMD/L),
        ip6tables -A INPUT -i lo -j ACCEPT
        ip6tables -A OUTPUT -o lo -j ACCEPT
        ip6tables -A INPUT -s ::1 -j DROP
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        ip6tables -L INPUT -v -n
        ip6tables -L OUTPUT -v -n
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
}
