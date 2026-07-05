# JR2.C.4.2.16 (CIS Level 1) — Ensure SSH MaxAuthTries is set to 4 or less.
# Generated from the SABC referential. Enforcement is the family's own
# Configure procedure, run only when the Validate procedure fails.
class sabc_hardening::jr2_c_4_2_16 {
  if $facts['os']['family'] == 'Debian' {
    exec { 'sabc_jr2_c_4_2_16_debian':
      command  => @(SABC_CMD/L),
        MaxAuthTries 4
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        sshd -T -C user=root -C host="$(hostname)" -C addr="$(grep $(hostname) /etc/hosts | awk '{print $1}')" | grep maxauthtries
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
  if $facts['os']['family'] == 'RedHat' {
    exec { 'sabc_jr2_c_4_2_16_redhat':
      command  => @(SABC_CMD/L),
        MaxAuthTries 4
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        sshd -T -C user=root -C host="$(hostname)" -C addr="$(grep $(hostname) /etc/hosts | awk '{print $1}')" | grep maxauthtries
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
}
