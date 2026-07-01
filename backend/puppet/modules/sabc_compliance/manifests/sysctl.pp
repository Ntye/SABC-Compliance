# == Define: sabc_compliance::sysctl
#
# Writes a sysctl drop-in under /etc/sysctl.d and reloads it. Dependency-free
# (no puppetlabs-sysctl needed on the airgapped master). Persists across reboots
# via the drop-in file and applies immediately via `sysctl --system`.
#
define sabc_compliance::sysctl (
  Hash[String, Variant[Integer, String]] $settings,
  String $filename = $title,
) {
  $body = $settings.map |$k, $v| { "${k} = ${v}" }.join("\n")

  file { "/etc/sysctl.d/${filename}.conf":
    ensure  => file,
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    content => "# Managed by SABC Compliance (CIS). Do not edit.\n${body}\n",
    notify  => Exec["sabc-sysctl-reload-${filename}"],
  }

  exec { "sabc-sysctl-reload-${filename}":
    command     => 'sysctl --system',
    path        => ['/usr/sbin', '/sbin', '/usr/bin', '/bin'],
    refreshonly => true,
  }
}
