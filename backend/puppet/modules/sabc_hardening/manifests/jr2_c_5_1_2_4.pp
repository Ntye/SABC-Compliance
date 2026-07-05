# JR2.C.5.1.2.4 (CIS Level 1) — Ensure rsyslog is not configured to receive logs from a remote client.
# Generated from the SABC referential. Enforcement is the family's own
# Configure procedure, run only when the Validate procedure fails.
class sabc_hardening::jr2_c_5_1_2_4 {
  if $facts['os']['family'] == 'Debian' {
    exec { 'sabc_jr2_c_5_1_2_4_debian':
      command  => @(SABC_CMD/L),
        $ModLoad imtcp
        $InputTCPServerRun
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        grep '$ModLoad imtcp' /etc/rsyslog.conf /etc/rsyslog.d/*.conf
        grep '$InputTCPServerRun' /etc/rsyslog.conf /etc/rsyslog.d/*.conf
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
  if $facts['os']['family'] == 'RedHat' {
    exec { 'sabc_jr2_c_5_1_2_4_redhat':
      command  => @(SABC_CMD/L),
        $ModLoad imtcp
        $InputTCPServerRun
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        grep '$ModLoad imtcp' /etc/rsyslog.conf /etc/rsyslog.d/*.conf
        grep '$InputTCPServerRun' /etc/rsyslog.conf /etc/rsyslog.d/*.conf
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
}
