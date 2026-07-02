# == Class: sabc_compliance::package_repo
#
# Enforces the OS package repository a node pulls from — the Puppet counterpart
# of the configure_package_repo.yml Ansible play, so once a master is up the
# repo is maintained on every `puppet agent -t` (it "goes into the rules").
#
# $repo is a hash: { name, url, suite, components, gpg_key } (enabled is checked
# by the caller). Uses only core Puppet types.
#
class sabc_compliance::package_repo (
  Hash $repo,
) {
  $repo_name  = $repo['name']
  $repo_url   = $repo['url']
  $repo_key   = $repo['gpg_key']
  $has_key    = ($repo_key =~ String and $repo_key != '')

  if $repo_name =~ String and $repo_name != '' and $repo_url =~ String and $repo_url != '' {

    if $facts['os']['family'] == 'Debian' {
      $suite = ($repo['suite'] =~ String and $repo['suite'] != '') ? {
        true    => $repo['suite'],
        default => $facts['os']['distro']['codename'],
      }
      $components = ($repo['components'] =~ String and $repo['components'] != '') ? {
        true    => $repo['components'],
        default => 'main',
      }

      if $has_key {
        exec { "sabc-repo-key-${repo_name}":
          command  => "curl -fsSL '${repo_key}' | gpg --dearmor -o '/usr/share/keyrings/${repo_name}.gpg'",
          path     => ['/usr/bin', '/bin'],
          creates  => "/usr/share/keyrings/${repo_name}.gpg",
          provider => 'shell',
          before   => File["/etc/apt/sources.list.d/${repo_name}.list"],
        }
        $signed_by = "[signed-by=/usr/share/keyrings/${repo_name}.gpg] "
      } else {
        $signed_by = ''
      }

      file { "/etc/apt/sources.list.d/${repo_name}.list":
        ensure  => file,
        owner   => 'root',
        group   => 'root',
        mode    => '0644',
        content => "# Managed by SABC Compliance.\ndeb ${signed_by}${repo_url} ${suite} ${components}\n",
        notify  => Exec["sabc-apt-update-${repo_name}"],
      }
      exec { "sabc-apt-update-${repo_name}":
        command     => 'apt-get update',
        path        => ['/usr/bin', '/bin'],
        refreshonly => true,
      }

    } else {
      # RedHat family — yumrepo is a core Puppet type.
      yumrepo { $repo_name:
        descr    => "${repo_name} (SABC managed)",
        baseurl  => $repo_url,
        enabled  => 1,
        gpgcheck => $has_key ? { true => 1, default => 0 },
        gpgkey   => $has_key ? { true => $repo_key, default => absent },
      }
    }
  }
}
