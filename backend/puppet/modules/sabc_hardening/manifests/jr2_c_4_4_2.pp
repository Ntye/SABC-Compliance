# JR2.C.4.4.2 (CIS Level 1) — Ensure lockout for failed password attempts is configured.
# Generated from the SABC referential. Enforcement is the family's own
# Configure procedure, run only when the Validate procedure fails.
class sabc_hardening::jr2_c_4_4_2 {
  if $facts['os']['family'] == 'Debian' {
    exec { 'sabc_jr2_c_4_4_2_debian':
      command  => @(SABC_CMD/L),
        auth required pam_tally2.so onerr=fail audit silent deny=5 unlock_time=900
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        grep 'pam_tally2' /etc/pam.d/common-auth
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
  if $facts['os']['family'] == 'RedHat' {
    exec { 'sabc_jr2_c_4_4_2_redhat':
      command  => @(SABC_CMD/L),
        printf 'minlen = 14\nminclass = 4\n' >> /etc/security/pwquality.conf
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        grep -P '^\h*(minlen|minclass|dcredit|ucredit|ocredit|lcredit)' /etc/security/pwquality.conf /etc/security/pwquality.conf.d/*.conf 2>/dev/null
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
}
