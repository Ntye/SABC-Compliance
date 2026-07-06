# JR2.C.4.3.3 (CIS Level 1) — Ensure sudo log file exists.
# Generated from the SABC referential. Enforcement is the family's own
# Configure procedure, run only when the Validate procedure fails.
class sabc_hardening::jr2_c_4_3_3 {
  if $facts['os']['family'] == 'Debian' {
    $cfg_debian = find_file('sabc_hardening/jr2_c_4_3_3_debian_cfg.sh')
    $chk_debian = find_file('sabc_hardening/jr2_c_4_3_3_debian_chk.sh')
    exec { 'sabc_jr2_c_4_3_3_debian':
      command   => "/bin/bash '${cfg_debian}' </dev/null",
      provider  => 'shell',
      path      => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
      unless    => "/bin/bash '${chk_debian}' </dev/null",
      logoutput => 'on_failure',
    }
  }
  if $facts['os']['family'] == 'RedHat' {
    $cfg_redhat = find_file('sabc_hardening/jr2_c_4_3_3_redhat_cfg.sh')
    $chk_redhat = find_file('sabc_hardening/jr2_c_4_3_3_redhat_chk.sh')
    exec { 'sabc_jr2_c_4_3_3_redhat':
      command   => "/bin/bash '${cfg_redhat}' </dev/null",
      provider  => 'shell',
      path      => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
      unless    => "/bin/bash '${chk_redhat}' </dev/null",
      logoutput => 'on_failure',
    }
  }
}
