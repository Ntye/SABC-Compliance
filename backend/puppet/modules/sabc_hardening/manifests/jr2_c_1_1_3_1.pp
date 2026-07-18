# JR2.C.1.1.3.1 (CIS Level 2) — Ensure nodev option set on /var partition.
# Generated from the SABC referential. Enforcement is the family's own
# Configure procedure, run only when the Validate procedure fails.
class sabc_hardening::jr2_c_1_1_3_1 {
  if $facts['os']['family'] == 'RedHat' {
    $cfg_redhat = find_file('sabc_hardening/jr2_c_1_1_3_1_redhat_cfg.sh')
    $chk_redhat = find_file('sabc_hardening/jr2_c_1_1_3_1_redhat_chk.sh')
    exec { 'sabc_jr2_c_1_1_3_1_redhat':
      command   => "/bin/bash '${cfg_redhat}' </dev/null",
      provider  => 'shell',
      path      => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
      unless    => "/bin/bash '${chk_redhat}' </dev/null || [ \$? -eq 101 ]",
      logoutput => 'on_failure',
    }
  }
}
