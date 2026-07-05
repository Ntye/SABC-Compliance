# JR2.C.3.4.2.3 (CIS Level 1) — Ensure a nftables table exists.
# Generated from the SABC referential. Enforcement is the family's own
# Configure procedure, run only when the Validate procedure fails.
class sabc_hardening::jr2_c_3_4_2_3 {
  if $facts['os']['family'] == 'Debian' {
    exec { 'sabc_jr2_c_3_4_2_3_debian':
      command  => @(SABC_CMD/L),
        nft create table inet
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        nft list tables
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
  if $facts['os']['family'] == 'RedHat' {
    exec { 'sabc_jr2_c_3_4_2_3_redhat':
      command  => @(SABC_CMD/L),
        nft create table inet
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        nft list tables
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
}
