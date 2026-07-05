# JR2.C.4.2.17 (CIS Level 1) — Ensure SSH MaxStartups is configured.
# Generated from the SABC referential. Enforcement is the family's own
# Configure procedure, run only when the Validate procedure fails.
class sabc_hardening::jr2_c_4_2_17 {
  if $facts['os']['family'] == 'Debian' {
    exec { 'sabc_jr2_c_4_2_17_debian':
      command  => @(SABC_CMD/L),
        MaxStartups 10:30:60
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        sshd -T -C user=root -C host="$(hostname)" -C addr="$(grep $(hostname) /etc/hosts | awk '{print $1}')" | grep -i maxstartups
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
  if $facts['os']['family'] == 'RedHat' {
    exec { 'sabc_jr2_c_4_2_17_redhat':
      command  => @(SABC_CMD/L),
        MaxStartups 10:30:60
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        sshd -T -C user=root -C host="$(hostname)" -C addr="$(grep $(hostname) /etc/hosts | awk '{print $1}')" | grep -i maxstartups
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
}
