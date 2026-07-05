# JR2.C.2.2.9 (CIS Level 1) — Ensure IMAP and POP3 server are not installed.
# Generated from the SABC referential. Enforcement is the family's own
# Configure procedure, run only when the Validate procedure fails.
class sabc_hardening::jr2_c_2_2_9 {
  if $facts['os']['family'] == 'Debian' {
    exec { 'sabc_jr2_c_2_2_9_debian':
      command  => @(SABC_CMD/L),
        apt purge dovecot-imapd dovecot-pop3d
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        dpkg-query -W -f='${binary:Package}\t${Status}\t${db:Status-Status}\n' dovecot-imapd dovecot-pop3d
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
  if $facts['os']['family'] == 'RedHat' {
    exec { 'sabc_jr2_c_2_2_9_redhat':
      command  => @(SABC_CMD/L),
        dnf remove -y dovecot-imapd dovecot-pop3d
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        rpm -q dovecot-imapd dovecot-pop3d
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
}
