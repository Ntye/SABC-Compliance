# JR2.C.3.4.3.2.2 (CIS Level 1) — Ensure iptables loopback traffic is configured.
# Generated from the SABC referential. Enforcement is the family's own
# Configure procedure, run only when the Validate procedure fails.
class sabc_hardening::jr2_c_3_4_3_2_2 {
  if $facts['os']['family'] == 'Debian' {
    exec { 'sabc_jr2_c_3_4_3_2_2_debian':
      command  => @(SABC_CMD/L),
        iptables -A INPUT -i lo -j ACCEPT
        iptables -A OUTPUT -o lo -j ACCEPT
        iptables -A INPUT -s 127.0.0.0/8 -j DROP
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        iptables -L INPUT -v -n
        iptables -L OUTPUT -v -n
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
  if $facts['os']['family'] == 'RedHat' {
    exec { 'sabc_jr2_c_3_4_3_2_2_redhat':
      command  => @(SABC_CMD/L),
        iptables -A INPUT -i lo -j ACCEPT
        iptables -A OUTPUT -o lo -j ACCEPT
        iptables -A INPUT -s 127.0.0.0/8 -j DROP
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        iptables -L INPUT -v -n
        iptables -L OUTPUT -v -n
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
}
