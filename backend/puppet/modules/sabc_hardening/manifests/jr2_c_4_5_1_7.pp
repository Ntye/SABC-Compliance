# JR2.C.4.5.1.7 (CIS Level 1) — Ensure preventing the use of dictionary words for passwords is configured.
# Generated from the SABC referential. Enforcement is the family's own
# Configure procedure, run only when the Validate procedure fails.
class sabc_hardening::jr2_c_4_5_1_7 {
  if $facts['os']['family'] == 'Debian' {
    exec { 'sabc_jr2_c_4_5_1_7_debian':
      command  => @(SABC_CMD/L),
        dictcheck = 1
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        grep -Pi '^\h*dictcheck\h*=\h*[^0]' /etc/security/pwquality.conf
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
  if $facts['os']['family'] == 'RedHat' {
    exec { 'sabc_jr2_c_4_5_1_7_redhat':
      command  => @(SABC_CMD/L),
        dictcheck = 1
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        grep -Pi '^\h*dictcheck\h*=\h*[^0]' /etc/security/pwquality.conf
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
}
