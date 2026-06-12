# encoding: utf-8
# CIS Benchmark — Section 2: Services
# Remove or disable special-purpose services and insecure clients, and ensure
# time synchronization is in place.

title 'Section 2 — Services'

# 2.1.1 Time synchronization
control 'cis-2.1.1-time-sync' do
  impact 0.5
  title 'Ensure a time synchronization daemon is in use'
  desc 'A running NTP/chrony/timesyncd daemon keeps clocks (and log timestamps) accurate.'
  tag cis: '2.1.1'
  tag iso27001: 'A.12.4.4'
  describe.one do
    describe service('chronyd') do
      it { should be_running }
    end
    describe service('chrony') do
      it { should be_running }
    end
    describe service('systemd-timesyncd') do
      it { should be_running }
    end
    describe service('ntp') do
      it { should be_running }
    end
    describe service('ntpd') do
      it { should be_running }
    end
  end
end

# 2.1.2 xinetd super-server
control 'cis-2.1.2-xinetd' do
  impact 0.4
  title 'Ensure xinetd is not installed'
  desc 'The legacy xinetd super-server should not be present.'
  tag cis: '2.1.2'
  describe package('xinetd') do
    it { should_not be_installed }
  end
end

# 2.2 Special-purpose services that must not be installed on a hardened host
{
  'avahi'        => %w(avahi-daemon avahi),
  'cups'         => %w(cups),
  'dhcp'         => %w(isc-dhcp-server dhcp-server dhcp),
  'ldap-server'  => %w(slapd openldap-servers),
  'nfs'          => %w(nfs-kernel-server nfs-utils),
  'dns'          => %w(bind9 bind),
  'ftp'          => %w(vsftpd ftp),
  'http'         => %w(apache2 httpd),
  'imap-pop3'    => %w(dovecot-imapd dovecot),
  'samba'        => %w(samba smb),
  'http-proxy'   => %w(squid),
  'snmp'         => %w(snmpd net-snmp),
  'nis'          => %w(ypserv),
  'telnet-server'=> %w(telnetd telnet-server),
  'tftp-server'  => %w(tftpd tftp-server),
  'rsync'        => %w(rsync-daemon rsyncd),
}.each do |label, pkgs|
  control "cis-2.2-#{label}" do
    impact 0.6
    title "Ensure #{label} server is not installed"
    desc "The #{label} service should not be installed on a hardened host unless explicitly required."
    tag cis: '2.2'
    tag pci_dss: '2.2.3'
    pkgs.each do |p|
      describe package(p) do
        it { should_not be_installed }
      end
    end
  end
end

control 'cis-2.2-mta-local-only' do
  impact 0.4
  title 'Ensure mail transfer agent is configured for local-only mode'
  desc 'The MTA must not listen on a non-loopback address unless the host is a mail server.'
  tag cis: '2.2.15'
  describe command("ss -lntu 2>/dev/null | awk '$5 ~ /:25$/ {print $5}' | grep -Ev '127.0.0.1|::1' || true") do
    its('stdout.strip') { should eq '' }
  end
end

# 2.3 Service clients
%w(telnet rsh-client talk ldap-utils nis tftp).each do |pkg|
  control "cis-2.3-client-#{pkg}" do
    impact 0.5
    title "Ensure #{pkg} client is not installed"
    desc "Insecure or unneeded client #{pkg} should be removed."
    tag cis: '2.3'
    describe package(pkg) do
      it { should_not be_installed }
    end
  end
end
