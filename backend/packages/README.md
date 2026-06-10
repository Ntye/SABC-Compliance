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

### wazuh-manager/

The playbook uses the official `wazuh-install.sh` all-in-one installer and
supports full offline (airgap) installation on both Debian and RPM targets.

| What you put here | Mode |
|---|---|
| `wazuh-install.sh` + `wazuh-offline-deb.tar.gz` | **AIRGAP** on Debian/Ubuntu |
| `wazuh-install.sh` + `wazuh-offline-rpm.tar.gz` | **AIRGAP** on RHEL/Rocky/CentOS |
| `wazuh-install.sh` + `wazuh-offline.tar.gz` | **AIRGAP** fallback (single-OS, must match target) |
| + `wazuh-install-files.tar` (optional) | skips certificate generation on target |
| *(empty or script only)* | **ONLINE** — downloads packages from packages.wazuh.com |

**Naming priority**: OS-specific names (`wazuh-offline-deb.tar.gz` /
`wazuh-offline-rpm.tar.gz`) take precedence; `wazuh-offline.tar.gz` is
the fallback so a single downloaded file works out of the box.

**Build the offline archives** (run once on any internet-connected Linux machine):

```bash
# Download the installer (use version-specific URL for a fixed release):
curl -sO https://packages.wazuh.com/4.x/wazuh-install.sh
# or for a pinned version:
# curl -sO https://packages.wazuh.com/4.14/wazuh-install.sh

# Build the Debian/Ubuntu offline archive:
bash wazuh-install.sh --download-packages deb
mv wazuh-offline.tar.gz packages/wazuh-manager/wazuh-offline-deb.tar.gz

# Build the RHEL/Rocky/CentOS offline archive:
bash wazuh-install.sh --download-packages rpm
mv wazuh-offline.tar.gz packages/wazuh-manager/wazuh-offline-rpm.tar.gz

# Copy the installer script:
cp wazuh-install.sh packages/wazuh-manager/
```

**Optional — pre-generate certificates** (avoids running cert-gen on the target):

```bash
# 1. Create config.yml (substitute the actual IP of your Wazuh server node):
cat > config.yml << 'EOF'
nodes:
  indexer:
    - name: wazuh-indexer
      ip: "192.0.2.10"
  server:
    - name: wazuh-server
      ip: "192.0.2.10"
  dashboard:
    - name: wazuh-dashboard
      ip: "192.0.2.10"
EOF

# 2. Generate certificates and config bundle:
bash wazuh-install.sh --generate-config-files
# Creates: wazuh-install-files.tar

# 3. Copy to packages directory:
cp wazuh-install-files.tar packages/wazuh-manager/
```

> **Note on IP addresses in certificates:**  The certificates embed the node
> IP as a Subject Alternative Name.  On EC2 instances whose public IP changes
> on stop/start, either use the private IP (stable) or regenerate
> `wazuh-install-files.tar` after each IP change and re-run the install job.

### wazuh-agent/

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

### Puppet Server + Agent (.rpm, Rocky Linux 9)

```bash
yum install --downloadonly --downloaddir=packages/puppet-master \
    puppetserver java-17-openjdk-headless

yum install --downloadonly --downloaddir=packages/puppet-agent puppet-agent
```

### Wazuh Agent (.deb, Ubuntu)

```bash
# Add Wazuh repo on an internet-connected machine, then:
curl -s https://packages.wazuh.com/key/GPG-KEY-WAZUH | apt-key add -
echo "deb https://packages.wazuh.com/4.x/apt/ stable main" \
     > /etc/apt/sources.list.d/wazuh.list
apt-get update
apt-get download wazuh-agent
mv wazuh-agent_*.deb packages/wazuh-agent/
```

### Wazuh Agent (.rpm, Rocky Linux / RHEL)

```bash
rpm --import https://packages.wazuh.com/key/GPG-KEY-WAZUH
cat > /etc/yum.repos.d/wazuh.repo << 'EOF'
[wazuh]
name=Wazuh repository
baseurl=https://packages.wazuh.com/4.x/yum/
gpgcheck=1
gpgkey=https://packages.wazuh.com/key/GPG-KEY-WAZUH
enabled=1
EOF
yum install --downloadonly --downloaddir=packages/wazuh-agent wazuh-agent
```

> **Note:** The wazuh-manager is now installed using `wazuh-install.sh`
> (all-in-one with indexer + dashboard), not a single .deb/.rpm package.
> The `.deb`/`.rpm` approach above is only for the **agent** packages.
