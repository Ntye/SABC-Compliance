# JR2.C.4.2.17 (CIS Level 1) — Ensure SSH MaxStartups is configured.
# Generated from the SABC referential. Enforcement is the family's own
# Configure procedure, run only when the Validate procedure fails.
class sabc_hardening::jr2_c_4_2_17 {
  if $facts['os']['family'] == 'RedHat' {
    $cfg_redhat = find_file('sabc_hardening/jr2_c_4_2_17_redhat_cfg.sh')
    $chk_redhat = find_file('sabc_hardening/jr2_c_4_2_17_redhat_chk.sh')
    exec { 'sabc_jr2_c_4_2_17_redhat':
      command   => "/bin/bash '${cfg_redhat}' </dev/null",
      provider  => 'shell',
      path      => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
      unless    => "/bin/bash '${chk_redhat}' </dev/null || [ \$? -eq 101 ]",
      logoutput => 'on_failure',
    }
  }
}
