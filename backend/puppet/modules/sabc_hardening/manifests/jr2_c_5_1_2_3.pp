# JR2.C.5.1.2.3 (CIS Level 1) — Ensure rsyslog default file permissions are configured.
# Generated from the SABC referential. Enforcement is the family's own
# Configure procedure, run only when the Validate procedure fails.
class sabc_hardening::jr2_c_5_1_2_3 {
  if $facts['os']['family'] == 'Debian' {
    exec { 'sabc_jr2_c_5_1_2_3_debian':
      command  => @(SABC_CMD/L),
        $FileCreateMode 0640
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        grep ^\$FileCreateMode /etc/rsyslog.conf /etc/rsyslog.d/*.conf
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
  if $facts['os']['family'] == 'RedHat' {
    exec { 'sabc_jr2_c_5_1_2_3_redhat':
      command  => @(SABC_CMD/L),
        $FileCreateMode 0640
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        grep ^\$FileCreateMode /etc/rsyslog.conf /etc/rsyslog.d/*.conf
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
}
