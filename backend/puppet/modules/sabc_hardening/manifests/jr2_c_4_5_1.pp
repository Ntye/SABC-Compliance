# JR2.C.4.5.1 (CIS Level 1) — Ensure default group for the root account is GID 0.
# Generated from the SABC referential. Enforcement is the family's own
# Configure procedure, run only when the Validate procedure fails.
class sabc_hardening::jr2_c_4_5_1 {
  if $facts['os']['family'] == 'Debian' {
    exec { 'sabc_jr2_c_4_5_1_debian':
      command  => @(SABC_CMD/L),
        usermod -g 0 root
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        grep "^root:" /etc/passwd | cut -f4 -d:
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
  if $facts['os']['family'] == 'RedHat' {
    exec { 'sabc_jr2_c_4_5_1_redhat':
      command  => @(SABC_CMD/L),
        usermod -g 0 root
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        grep "^root:" /etc/passwd | cut -f4 -d:
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
}
