# JR2.C.6.2.4 (CIS Level 1) — Ensure shadow group is empty.
# Generated from the SABC referential. Enforcement is the family's own
# Configure procedure, run only when the Validate procedure fails.
class sabc_hardening::jr2_c_6_2_4 {
  if $facts['os']['family'] == 'Debian' {
    exec { 'sabc_jr2_c_6_2_4_debian':
      command  => @(SABC_CMD/L),
        sed -ri 's/(^shadow:[^:]*:[^:]*:)([^:]+$)/\1/' /etc/group
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        awk -F: '($1=="shadow") {print $NF}' /etc/group
        awk -F: -v GID="$(awk -F: '($1=="shadow") {print $3}' /etc/group)" '($4==GID) {print $1}' /etc/passwd
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
  if $facts['os']['family'] == 'RedHat' {
    exec { 'sabc_jr2_c_6_2_4_redhat':
      command  => @(SABC_CMD/L),
        sed -ri 's/(^shadow:[^:]*:[^:]*:)([^:]+$)/\1/' /etc/group
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        awk -F: '($1=="shadow") {print $NF}' /etc/group
        awk -F: -v GID="$(awk -F: '($1=="shadow") {print $3}' /etc/group)" '($4==GID) {print $1}' /etc/passwd
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
}
