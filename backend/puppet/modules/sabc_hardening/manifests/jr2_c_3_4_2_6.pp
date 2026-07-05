# JR2.C.3.4.2.6 (CIS Level 1) — Ensure nftables default deny firewall policy.
# Generated from the SABC referential. Enforcement is the family's own
# Configure procedure, run only when the Validate procedure fails.
class sabc_hardening::jr2_c_3_4_2_6 {
  if $facts['os']['family'] == 'Debian' {
    exec { 'sabc_jr2_c_3_4_2_6_debian':
      command  => @(SABC_CMD/L),
        nft chain
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        nft list ruleset | grep 'hook input'
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
  if $facts['os']['family'] == 'RedHat' {
    exec { 'sabc_jr2_c_3_4_2_6_redhat':
      command  => @(SABC_CMD/L),
        nft chain
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        nft list ruleset | grep 'hook input'
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
}
