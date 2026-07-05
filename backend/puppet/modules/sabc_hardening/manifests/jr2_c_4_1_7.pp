# JR2.C.4.1.7 (CIS Level 1) — Ensure permissions on /etc/cron.d are configured.
# Generated from the SABC referential. Enforcement is the family's own
# Configure procedure, run only when the Validate procedure fails.
class sabc_hardening::jr2_c_4_1_7 {
  if $facts['os']['family'] == 'Debian' {
    exec { 'sabc_jr2_c_4_1_7_debian':
      command  => @(SABC_CMD/L),
        chown root:root /etc/cron.d/
        chmod og-rwx /etc/cron.d/
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        stat -Lc 'Access: (%a/%A) Uid: ( %u/ %U) Gid: ( %g/ %G)' /etc/cron.d/
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
  if $facts['os']['family'] == 'RedHat' {
    exec { 'sabc_jr2_c_4_1_7_redhat':
      command  => @(SABC_CMD/L),
        chown root:root /etc/cron.d/
        chmod og-rwx /etc/cron.d/
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        stat -Lc 'Access: (%a/%A) Uid: ( %u/ %U) Gid: ( %g/ %G)' /etc/cron.d/
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
}
