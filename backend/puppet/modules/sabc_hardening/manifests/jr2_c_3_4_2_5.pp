# JR2.C.3.4.2.5 (CIS Level 1) — Ensure nftables loopback traffic is configured.
# Generated from the SABC referential. Enforcement is the family's own
# Configure procedure, run only when the Validate procedure fails.
class sabc_hardening::jr2_c_3_4_2_5 {
  if $facts['os']['family'] == 'Debian' {
    exec { 'sabc_jr2_c_3_4_2_5_debian':
      command  => @(SABC_CMD/L),
        nft add rule inet filter input iif lo accept
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        nft list ruleset | awk '/hook input/,/}/' | grep 'iif "lo" accept'
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
  if $facts['os']['family'] == 'RedHat' {
    exec { 'sabc_jr2_c_3_4_2_5_redhat':
      command  => @(SABC_CMD/L),
        nft add rule inet filter input iif lo accept
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        nft list ruleset | awk '/hook input/,/}/' | grep 'iif "lo" accept'
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
}
