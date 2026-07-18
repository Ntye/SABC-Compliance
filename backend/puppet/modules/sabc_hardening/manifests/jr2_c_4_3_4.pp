# JR2.C.4.3.4 (CIS Level 1) — Ensure re-authentication for privilege escalation is not disabled globally.
# Generated from the SABC referential. Enforcement is the family's own
# Configure procedure, run only when the Validate procedure fails.
class sabc_hardening::jr2_c_4_3_4 {
  if $facts['os']['family'] == 'Debian' {
    $cfg_debian = find_file('sabc_hardening/jr2_c_4_3_4_debian_cfg.sh')
    $chk_debian = find_file('sabc_hardening/jr2_c_4_3_4_debian_chk.sh')
    exec { 'sabc_jr2_c_4_3_4_debian':
      command   => "/bin/bash '${cfg_debian}' </dev/null",
      provider  => 'shell',
      path      => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
      unless    => "/bin/bash '${chk_debian}' </dev/null || [ \$? -eq 101 ]",
      logoutput => 'on_failure',
    }
  }
}
