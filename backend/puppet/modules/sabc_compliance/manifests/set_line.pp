# == Define: sabc_compliance::set_line
#
# Idempotently set "KEY<sep>VALUE" in a config file: replace the existing KEY
# line (whether "=" or whitespace separated) or append it if absent. Used for
# files that have no drop-in mechanism (auditd.conf, login.defs). Dependency-free
# — no puppetlabs-stdlib file_line, no augeas lens.
#
# The replace/append shell was validated for idempotency before shipping.
#
define sabc_compliance::set_line (
  String $path,
  String $key,
  String $value,
  String $sep = ' = ',
) {
  exec { "sabc-setline-${title}":
    command  => "if grep -Eq '^[[:space:]]*${key}([[:space:]]|=)' '${path}'; then sed -ri 's#^[[:space:]]*${key}([[:space:]]*=|[[:space:]]).*#${key}${sep}${value}#' '${path}'; else printf '%s\\n' '${key}${sep}${value}' >> '${path}'; fi",
    onlyif   => "test -f '${path}'",
    unless   => "grep -Eq '^[[:space:]]*${key}[[:space:]]*=?[[:space:]]*${value}([[:space:]]|\$)' '${path}'",
    path     => ['/usr/bin', '/bin', '/usr/sbin', '/sbin'],
    provider => 'shell',
  }
}
