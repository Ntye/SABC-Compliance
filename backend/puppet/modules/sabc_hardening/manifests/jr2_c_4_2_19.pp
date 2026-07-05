# JR2.C.4.2.19 (CIS Level 1) — Ensure SSH MaxSessions is set to 10 or less.
# Generated from the SABC referential. Enforcement is the family's own
# Configure procedure, run only when the Validate procedure fails.
class sabc_hardening::jr2_c_4_2_19 {
  if $facts['os']['family'] == 'Debian' {
    exec { 'sabc_jr2_c_4_2_19_debian':
      command  => @(SABC_CMD/L),
        MaxSessions 10
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        sshd -T -C user=root -C host="$(hostname)" -C addr="$(grep $(hostname) /etc/hosts | awk '{print $1}')" | grep -i maxsessions
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
  if $facts['os']['family'] == 'RedHat' {
    exec { 'sabc_jr2_c_4_2_19_redhat':
      command  => @(SABC_CMD/L),
        MaxSessions 10
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        sshd -T -C user=root -C host="$(hostname)" -C addr="$(grep $(hostname) /etc/hosts | awk '{print $1}')" | grep -i maxsessions
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
}
