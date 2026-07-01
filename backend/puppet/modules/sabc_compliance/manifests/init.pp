# == Class: sabc_compliance
#
# Enforces the SABC internal referential — a CIS Linux Benchmark — on a managed
# node. This is the "enforcement" half of the platform's closed remediation
# loop: Wazuh (or the operator) detects drift, the platform runs
# `puppet agent -t`, and the classes below bring the node back into compliance.
#
# Design principles (read before changing a default):
#   * Idempotent & convergent — every resource can run repeatedly with no churn.
#   * Safe-by-default — controls that could sever access (host firewall) or break
#     a legitimately-running service (removing apache/nfs) are gated behind
#     opt-in flags. The defaults harden without risking a lockout on the
#     key-based automation account the platform relies on.
#   * The "ansible" automation account's passwordless sudo is an APPROVED
#     exception in the referential (control sabc-5.3.5). This module NEVER
#     touches it. `remove_other_nopasswd` only ever removes OTHER accounts'
#     NOPASSWD grants, and only when explicitly enabled.
#   * Detective-only controls (world-writable files, unowned files, duplicate
#     UIDs, partition layout) are intentionally NOT auto-remediated — blindly
#     chmod-ing arbitrary files or repartitioning a live host is more dangerous
#     than the finding. Those remain visible in the scan report.
#
# Parameters let the platform/Hiera tune enforcement per node or per group.
#
class sabc_compliance (
  # Master switch — set false to make the whole module a no-op.
  Boolean $enforce                 = true,

  # Per-section toggles (all safe controls on by default).
  Boolean $manage_initial_setup    = true,
  Boolean $manage_services         = true,
  Boolean $manage_network          = true,
  Boolean $manage_logging_audit    = true,
  Boolean $manage_access_auth      = true,
  Boolean $manage_maintenance      = true,

  # Potentially disruptive controls — opt-in.
  #   manage_firewall: install + enable a host firewall. Even when true we ALWAYS
  #     add an allow rule for the SSH port FIRST so enabling it cannot lock the
  #     platform out. Default true because an explicit SSH allow makes it safe.
  Boolean $manage_firewall         = true,
  Integer $ssh_port                = 22,
  #   purge_insecure_servers: remove server packages (apache/nfs/samba/…). Off by
  #     default — a host may legitimately run one of these. Insecure *clients*
  #     (telnet, rsh) are always removed regardless (they are never needed).
  Boolean $purge_insecure_servers  = false,
  #   manage_sshd: harden sshd via a validated drop-in. Safe with key auth.
  Boolean $manage_sshd             = true,
  #   manage_pam: edit PAM (password hashing, su restriction, faillock). PAM
  #     mistakes can lock accounts, so this is conservative and on by default
  #     only for the low-risk pieces; su restriction is separately gated.
  Boolean $manage_pam              = true,
  Boolean $restrict_su             = false,
  #   remove_other_nopasswd: strip NOPASSWD sudo from accounts OTHER than the
  #     approved automation user. Dangerous (could disrupt other automation) →
  #     off by default. The ansible account is NEVER affected.
  Boolean $remove_other_nopasswd   = false,
  String  $automation_user         = 'ansible',
  #   manage_kernel_modules: blacklist unused filesystem/network modules. On
  #     Ubuntu, squashfs backs snapd — exclude it there by default.
  Boolean $manage_kernel_modules   = true,
  #   manage_aide: install the AIDE file-integrity package.
  Boolean $manage_aide             = true,

  # Password-policy values (login.defs / pwquality).
  Integer $pass_max_days           = 365,
  Integer $pass_min_days           = 1,
  Integer $pass_warn_age           = 7,
  Integer $pwquality_minlen        = 14,
  String  $login_umask             = '027',
) {

  if $enforce {
    # OS-family-aware defaults (service/package names differ Debian vs RedHat).
    include sabc_compliance::params

    if $manage_initial_setup {
      class { 'sabc_compliance::initial_setup': }
    }
    if $manage_services {
      class { 'sabc_compliance::services': }
    }
    if $manage_network {
      class { 'sabc_compliance::network': }
    }
    if $manage_logging_audit {
      class { 'sabc_compliance::logging_audit': }
    }
    if $manage_access_auth {
      class { 'sabc_compliance::access_auth': }
    }
    if $manage_maintenance {
      class { 'sabc_compliance::maintenance': }
    }
  }
}
