# == Class: sabc_compliance::logging_audit
#
# CIS Section 4 — Logging and Auditing. Installs and enables auditd, bounds and
# preserves the audit logs, installs the key CIS audit watch rules, and ensures
# a system logging service is running.
#
class sabc_compliance::logging_audit {
  include sabc_compliance::params

  # 4.1.1.1 auditd installed.
  package { $sabc_compliance::params::auditd_package:
    ensure => installed,
  }

  # 4.1.1.2 auditd enabled and running.
  service { 'auditd':
    ensure  => running,
    enable  => true,
    require => Package[$sabc_compliance::params::auditd_package],
  }

  # 4.1.2.1 Bound each audit log file (>= 8 MB). 4.1.2.2 Keep logs, never delete.
  sabc_compliance::set_line { 'auditd-max-log-file':
    path    => '/etc/audit/auditd.conf',
    key     => 'max_log_file',
    value   => '8',
    require => Package[$sabc_compliance::params::auditd_package],
    notify  => Service['auditd'],
  }
  sabc_compliance::set_line { 'auditd-max-log-file-action':
    path    => '/etc/audit/auditd.conf',
    key     => 'max_log_file_action',
    value   => 'keep_logs',
    require => Package[$sabc_compliance::params::auditd_package],
    notify  => Service['auditd'],
  }

  # 4.1.3 Key audit watch rules (identity, sudoers, login records, time changes).
  file { '/etc/audit/rules.d/sabc-cis.rules':
    ensure  => file,
    owner   => 'root',
    group   => 'root',
    mode    => '0640',
    content => @("RULES"),
      # Managed by SABC Compliance (CIS Section 4). Do not edit.
      -w /etc/group -p wa -k identity
      -w /etc/passwd -p wa -k identity
      -w /etc/shadow -p wa -k identity
      -w /etc/gshadow -p wa -k identity
      -w /etc/sudoers -p wa -k scope
      -w /etc/sudoers.d -p wa -k scope
      -w /var/log/lastlog -p wa -k logins
      -w /var/log/faillog -p wa -k logins
      -a always,exit -F arch=b64 -S adjtimex,settimeofday,clock_settime -k time-change
      -a always,exit -F arch=b32 -S adjtimex,settimeofday,clock_settime -k time-change
      | RULES
    require => Package[$sabc_compliance::params::auditd_package],
    notify  => Exec['sabc-auditd-load-rules'],
  }

  # Load the rules into the running kernel. augenrules merges rules.d and loads;
  # fall back to auditctl / a service restart. returns [0,1] so a benign "no
  # change" exit never fails the run.
  exec { 'sabc-auditd-load-rules':
    command     => 'augenrules --load || auditctl -R /etc/audit/rules.d/sabc-cis.rules || systemctl restart auditd',
    path        => ['/usr/sbin', '/sbin', '/usr/bin', '/bin'],
    refreshonly => true,
    returns     => [0, 1],
  }

  # 4.2.1 A system logging service must be running (rsyslog satisfies the check
  # on both families; journald also runs but rsyslog is the CIS-expected daemon).
  package { 'rsyslog':
    ensure => installed,
  }
  service { 'rsyslog':
    ensure  => running,
    enable  => true,
    require => Package['rsyslog'],
  }
}
