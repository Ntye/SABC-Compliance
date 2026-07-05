# JR2.C.2.2.16 (CIS Level 1) — Ensure rsync service is either not installed or is masked.
# Generated from the SABC referential. Enforcement is the family's own
# Configure procedure, run only when the Validate procedure fails.
class sabc_hardening::jr2_c_2_2_16 {
  if $facts['os']['family'] == 'Debian' {
    exec { 'sabc_jr2_c_2_2_16_debian':
      command  => @(SABC_CMD/L),
        apt purge rsync
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        dpkg-query -W -f='${binary:Package}\t${Status}\t${db:Status-Status}\n' rsync
        
        rsync unknown ok not-installed not-installed
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
  if $facts['os']['family'] == 'RedHat' {
    exec { 'sabc_jr2_c_2_2_16_redhat':
      command  => @(SABC_CMD/L),
        dnf remove -y rsync
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        rpm -q rsync
        rsync unknown ok not-installed not-installed
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
}
