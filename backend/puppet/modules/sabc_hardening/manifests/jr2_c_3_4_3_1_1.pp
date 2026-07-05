# JR2.C.3.4.3.1.1 (CIS Level 1) — Ensure iptables packages are installed.
# Generated from the SABC referential. Enforcement is the family's own
# Configure procedure, run only when the Validate procedure fails.
class sabc_hardening::jr2_c_3_4_3_1_1 {
  if $facts['os']['family'] == 'Debian' {
    exec { 'sabc_jr2_c_3_4_3_1_1_debian':
      command  => @(SABC_CMD/L),
        apt install iptables iptables-persistent
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        apt list iptables iptables-persistent | grep installed
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
  if $facts['os']['family'] == 'RedHat' {
    exec { 'sabc_jr2_c_3_4_3_1_1_redhat':
      command  => @(SABC_CMD/L),
        dnf install -y iptables iptables-persistent
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        apt list iptables iptables-persistent | grep installed
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
}
