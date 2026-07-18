# JR2.C.2.2.15 (CIS Level 1) — Ensure mail transfer agent is configured for local-only mode.
# Generated from the SABC referential. Enforcement is the family's own
# Configure procedure, run only when the Validate procedure fails.
class sabc_hardening::jr2_c_2_2_15 {
  if $facts['os']['family'] == 'RedHat' {
    $cfg_redhat = find_file('sabc_hardening/jr2_c_2_2_15_redhat_cfg.sh')
    $chk_redhat = find_file('sabc_hardening/jr2_c_2_2_15_redhat_chk.sh')
    exec { 'sabc_jr2_c_2_2_15_redhat':
      command   => "/bin/bash '${cfg_redhat}' </dev/null",
      provider  => 'shell',
      path      => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
      unless    => "/bin/bash '${chk_redhat}' </dev/null || [ \$? -eq 101 ]",
      logoutput => 'on_failure',
    }
  }
}
