# JR2.C.3.4.1.4 (CIS Level 1) — Ensure ufw loopback traffic is configured.
# Generated from the SABC referential. Enforcement is the family's own
# Configure procedure, run only when the Validate procedure fails.
class sabc_hardening::jr2_c_3_4_1_4 {
  if $facts['os']['family'] == 'Debian' {
    exec { 'sabc_jr2_c_3_4_1_4_debian':
      command  => @(SABC_CMD/L),
        ufw allow in on lo
        ufw allow out on lo
        ufw deny in from 127.0.0.0/8
        ufw deny in from ::1
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        ufw status verbose
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
  if $facts['os']['family'] == 'RedHat' {
    exec { 'sabc_jr2_c_3_4_1_4_redhat':
      command  => @(SABC_CMD/L),
        firewall-cmd --permanent --zone=trusted --add-interface=lo
        firewall-cmd --reload
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        firewall-cmd --get-zone-of-interface=lo
        firewall-cmd --list-all --zone=trusted
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
}
