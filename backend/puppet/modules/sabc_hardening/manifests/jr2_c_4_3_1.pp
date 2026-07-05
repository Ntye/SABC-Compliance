# JR2.C.4.3.1 (CIS Level 1) — Ensure sudo is installed.
# Generated from the SABC referential. Enforcement is the family's own
# Configure procedure, run only when the Validate procedure fails.
class sabc_hardening::jr2_c_4_3_1 {
  if $facts['os']['family'] == 'Debian' {
    exec { 'sabc_jr2_c_4_3_1_debian':
      command  => @(SABC_CMD/L),
        apt install sudo
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        dpkg-query -W sudo sudo-ldap > /dev/null 2>&1 && dpkg-query -W -f='${binary:Package}\t${Status}\t${db:Status-Status}\n' sudo sudo-ldap | awk '($4=="installed" && $NF=="installed") {print "\n""PASS:""\n""Package ""\""$1"\""" is installed""\n"}' || echo -e "\nFAIL:\nneither \"sudo\" or \"sudo-ldap\" package is installed\n"
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
  if $facts['os']['family'] == 'RedHat' {
    exec { 'sabc_jr2_c_4_3_1_redhat':
      command  => @(SABC_CMD/L),
        dnf install -y sudo
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        rpm -q sudo sudo-ldap > /dev/null 2>&1 && rpm -q sudo sudo-ldap | awk '($4=="installed" && $NF=="installed") {print "\n""PASS:""\n""Package ""\""$1"\""" is installed""\n"}' || echo -e "\nFAIL:\nneither \"sudo\" or \"sudo-ldap\" package is installed\n"
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
}
