# JR2.C.5.1.3.1 (CIS Level 1) — Ensure cryptographic mechanisms are used to protect the integrity of audit tools.
# Generated from the SABC referential. Enforcement is the family's own
# Configure procedure, run only when the Validate procedure fails.
class sabc_hardening::jr2_c_5_1_3_1 {
  if $facts['os']['family'] == 'Debian' {
    exec { 'sabc_jr2_c_5_1_3_1_debian':
      command  => @(SABC_CMD/L),
        Audit Tools
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        grep -Ps -- '(\/sbin\/(audit|au)\H*\b)' /etc/aide.conf /etc/aide/aide.conf /etc/aide.conf.d/*.conf /etc/aide/aide.conf.d/*
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
  if $facts['os']['family'] == 'RedHat' {
    exec { 'sabc_jr2_c_5_1_3_1_redhat':
      command  => @(SABC_CMD/L),
        Audit Tools
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        grep -Ps -- '(\/sbin\/(audit|au)\H*\b)' /etc/aide.conf /etc/aide/aide.conf /etc/aide.conf.d/*.conf /etc/aide/aide.conf.d/*
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
}
