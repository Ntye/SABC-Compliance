# Offline Packages (Airgap Mode)

Place pre-downloaded installation packages here to enable airgap (offline) installation.
When a subdirectory contains matching `.deb` or `.rpm` files, the playbook automatically
switches to airgap mode and uploads the files to the target node — no internet access needed.

If a subdirectory is empty, the playbook falls back to online installation via the
vendor's public repository.

## Directory layout

```
packages/
├── puppet-master/    ← puppetserver + openjdk packages
├── puppet-agent/     ← puppet-agent packages
├── wazuh-manager/    ← wazuh-manager packages
└── wazuh-agent/      ← wazuh-agent packages
```

## Naming convention

Files must match the glob patterns below (the playbooks use `find` with these patterns):

| Directory       | Pattern                         |
|-----------------|---------------------------------|
| puppet-master/  | `puppetserver*.deb` or `*.rpm`  |
| puppet-master/  | `openjdk*.deb` or `*.rpm` (Java)|
| puppet-agent/   | `puppet-agent*.deb` or `*.rpm`  |
| wazuh-manager/  | `wazuh-manager*.deb` or `*.rpm` |
| wazuh-agent/    | `wazuh-agent*.deb` or `*.rpm`   |

## What to download

### Puppet Server + Java (Ubuntu 22.04 example)

```bash
# Java 17 (puppetserver dependency)
apt-get download openjdk-17-jre-headless

# Puppet release package (sets up the apt repo — download for bootstrapping)
wget https://apt.puppet.com/puppet8-release-jammy.deb -O packages/puppet-master/puppet8-release-jammy.deb

# puppetserver itself (download from a machine that has the repo configured)
apt-get download puppetserver
mv puppetserver_*.deb packages/puppet-master/
```

### Puppet Agent (Ubuntu 22.04 example)

```bash
apt-get download puppet-agent
mv puppet-agent_*.deb packages/puppet-agent/
```

### Wazuh Manager (Ubuntu/Debian)

```bash
# Add repo first (on an internet-connected machine)
curl -s https://packages.wazuh.com/key/GPG-KEY-WAZUH | apt-key add -
echo "deb https://packages.wazuh.com/4.x/apt/ stable main" > /etc/apt/sources.list.d/wazuh.list
apt-get update
apt-get download wazuh-manager
mv wazuh-manager_*.deb packages/wazuh-manager/
```

### Wazuh Agent (Ubuntu/Debian)

```bash
apt-get download wazuh-agent
mv wazuh-agent_*.deb packages/wazuh-agent/
```

### Rocky Linux / RHEL (RPM)

```bash
# Puppet
wget https://yum.puppet.com/puppet8-release-el-9.noarch.rpm
yum install --downloadonly --downloaddir=packages/puppet-master puppetserver java-17-openjdk-headless
yum install --downloadonly --downloaddir=packages/puppet-agent puppet-agent

# Wazuh
rpm --import https://packages.wazuh.com/key/GPG-KEY-WAZUH
# create /etc/yum.repos.d/wazuh.repo then:
yum install --downloadonly --downloaddir=packages/wazuh-manager wazuh-manager
yum install --downloadonly --downloaddir=packages/wazuh-agent wazuh-agent
```

> **Tip:** The `yum install --downloadonly` command also downloads all dependencies.
> For apt, use `apt-get download` + `apt-rdepends` to pull the full dependency tree.
