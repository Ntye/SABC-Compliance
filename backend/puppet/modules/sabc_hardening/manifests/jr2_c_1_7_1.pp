# JR2.C.1.7.1 (CIS Level 1) — Ensure GDM login banner is configured.
# Generated from the SABC referential. Enforcement is the family's own
# Configure procedure, run only when the Validate procedure fails.
class sabc_hardening::jr2_c_1_7_1 {
  if $facts['os']['family'] == 'Debian' {
    $cfg_debian = find_file('sabc_hardening/jr2_c_1_7_1_debian_cfg.sh')
    $chk_debian = find_file('sabc_hardening/jr2_c_1_7_1_debian_chk.sh')
    exec { 'sabc_jr2_c_1_7_1_debian':
      command   => "/bin/bash '${cfg_debian}' </dev/null",
      provider  => 'shell',
      path      => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
      unless    => "/bin/bash '${chk_debian}' </dev/null",
      logoutput => 'on_failure',
    }
  }
  if $facts['os']['family'] == 'RedHat' {
    $cfg_redhat = find_file('sabc_hardening/jr2_c_1_7_1_redhat_cfg.sh')
    $chk_redhat = find_file('sabc_hardening/jr2_c_1_7_1_redhat_chk.sh')
    exec { 'sabc_jr2_c_1_7_1_redhat':
      command   => "/bin/bash '${cfg_redhat}' </dev/null",
      provider  => 'shell',
      path      => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
      unless    => "/bin/bash '${chk_redhat}' </dev/null",
      logoutput => 'on_failure',
    }
  }
}
