# Offline Packages

Place pre-downloaded packages here to control how each service is installed.
The playbooks scan these directories at run time and pick the best available mode.

## Installation modes (checked in order, first match wins)

### puppet-master/

| What you put here | Mode |
|---|---|
| `puppet-enterprise*.tar.gz` | **TARBALL** — runs the PE silent installer |
| `puppetserver*.deb` / `*.rpm` (+ optional `openjdk*.deb`) | **PACKAGES** — uploads and installs with apt/yum |
| `puppet*-release*.deb` / `*.rpm` only | **ONLINE** with local repo package (avoids downloading release pkg) |
| *(empty)* | **ONLINE** — downloads everything from apt.puppet.com |

### puppet-agent/

| What you put here | Mode |
|---|---|
| `puppet-agent*.deb` / `*.rpm` | **PACKAGES** — full offline, no internet |
| `puppet*-release*.deb` / `*.rpm` only | **LOCAL-REPO** — installs release pkg locally, pulls agent from repo |
| *(empty)* | **ONLINE** — downloads release pkg + agent from internet |

### Puppet Enterprise (tarball)

Download the installer from https://puppet.com/try-puppet/puppet-enterprise/download/
and place it in `puppet-master/`:
```
puppet-master/puppet-enterprise-2023.x.x-ubuntu-22.04-amd64.tar.gz
```

### Puppet Server + Agent (open source .deb, Ubuntu 22.04)

```bash
# On an internet-connected machine with the puppet repo already configured:
apt-get download puppetserver openjdk-17-jre-headless
mv puppetserver_*.deb openjdk*.deb packages/puppet-master/

apt-get download puppet-agent
mv puppet-agent_*.deb packages/puppet-agent/

# Or just drop the release package to use LOCAL-REPO mode:
wget https://apt.puppet.com/puppet8-release-jammy.deb \
     -O packages/puppet-agent/puppet8-release-jammy.deb
```

### detection-agent/

| What you put here | Mode |
|---|---|
| `watchdog*.whl` (+ deps) | **AIRGAP** — installed with `pip --no-index` |
| *(empty)* | **ONLINE** — distro `python3-watchdog` package, then pip |

### Puppet Server + Agent (.rpm, Rocky Linux 9)

```bash
yum install --downloadonly --downloaddir=packages/puppet-master \
    puppetserver java-17-openjdk-headless

yum install --downloadonly --downloaddir=packages/puppet-agent puppet-agent
```
