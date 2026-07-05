# JR2.C.3.4.1.6 (CIS Level 1) — Ensure ufw default deny firewall policy.
# Generated from the SABC referential. Enforcement is the family's own
# Configure procedure, run only when the Validate procedure fails.
class sabc_hardening::jr2_c_3_4_1_6 {
  if $facts['os']['family'] == 'Debian' {
    exec { 'sabc_jr2_c_3_4_1_6_debian':
      command  => @(SABC_CMD/L),
        ufw default deny incoming
        ufw default deny outgoing
        ufw default deny routed
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        ufw status verbose | grep Default:
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
  if $facts['os']['family'] == 'RedHat' {
    exec { 'sabc_jr2_c_3_4_1_6_redhat':
      command  => @(SABC_CMD/L),
        firewall-cmd --permanent --zone=$(firewall-cmd --get-default-zone) --set-target=DROP
        firewall-cmd --reload
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        firewall-cmd --get-default-zone
        firewall-cmd --permanent --zone=$(firewall-cmd --get-default-zone) --get-target
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
}
