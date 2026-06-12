# encoding: utf-8
# CIS Benchmark — Section 1: Initial Setup
# Filesystem configuration, secure boot settings, process hardening,
# mandatory access control and warning banners.

title 'Section 1 — Initial Setup'

# 1.1.1 Disable unused filesystem kernel modules
%w(cramfs freevxfs jffs2 hfs hfsplus squashfs udf usb-storage).each do |fs|
  control "cis-1.1.1-#{fs}" do
    impact 0.3
    title "Ensure mounting of #{fs} filesystems is disabled"
    desc "The #{fs} filesystem type should not be loadable unless there is a documented business need."
    tag cis: '1.1.1'
    tag iso27001: 'A.12.6.2'
    describe kernel_module(fs) do
      it { should_not be_loaded }
      it { should be_disabled }
    end
  end
end

# 1.1.2–1.1.8 Separate partitions with hardened mount options
{
  '/tmp'     => %w(nodev nosuid noexec),
  '/var'     => %w(),
  '/var/tmp' => %w(nodev nosuid noexec),
  '/var/log' => %w(),
  '/home'    => %w(nodev),
  '/dev/shm' => %w(nodev nosuid noexec),
}.each do |path, opts|
  control "cis-1.1-partition#{path.tr('/', '-')}" do
    impact 0.2
    title "Ensure #{path} is a separate partition with secure options"
    desc "#{path} should reside on its own partition; recommended mount options: #{opts.join(', ')}."
    tag cis: '1.1'
    describe mount(path) do
      it { should be_mounted }
    end
    opts.each do |opt|
      describe mount(path) do
        its('options') { should include opt }
      end
    end
  end
end

control 'cis-1.1.22-sticky-bit' do
  impact 0.4
  title 'Ensure sticky bit is set on all world-writable directories'
  desc 'World-writable directories must have the sticky bit set so users cannot delete files they do not own.'
  tag cis: '1.1.22'
  describe command("df --local -P 2>/dev/null | awk 'NR!=1 {print $6}' | xargs -I '{}' find '{}' -xdev -type d \\( -perm -0002 -a ! -perm -1000 \\) 2>/dev/null") do
    its('stdout.strip') { should eq '' }
  end
end

# 1.3 Filesystem integrity
control 'cis-1.3.1-aide-installed' do
  impact 0.5
  title 'Ensure a filesystem integrity checking tool (AIDE) is installed'
  desc 'AIDE detects unauthorized changes to files and directories.'
  tag cis: '1.3.1'
  tag iso27001: 'A.12.2.1'
  describe.one do
    describe package('aide') do
      it { should be_installed }
    end
    describe package('aide-common') do
      it { should be_installed }
    end
  end
end

# 1.4 Secure boot settings
control 'cis-1.4.1-bootloader-perms' do
  impact 0.5
  title 'Ensure bootloader configuration permissions are restricted'
  desc 'The GRUB configuration file must be owned by root and inaccessible to other users.'
  tag cis: '1.4.1'
  describe.one do
    describe file('/boot/grub2/grub.cfg') do
      its('owner') { should eq 'root' }
      it { should_not be_readable.by('other') }
    end
    describe file('/boot/grub/grub.cfg') do
      its('owner') { should eq 'root' }
      it { should_not be_readable.by('other') }
    end
  end
end

# 1.5 Additional process hardening
control 'cis-1.5.1-aslr' do
  impact 0.6
  title 'Ensure address space layout randomization (ASLR) is enabled'
  desc 'kernel.randomize_va_space must be 2 to randomize process memory layout.'
  tag cis: '1.5.1'
  tag iso27001: 'A.12.6.1'
  describe kernel_parameter('kernel.randomize_va_space') do
    its('value') { should eq 2 }
  end
end

control 'cis-1.5.2-ptrace-scope' do
  impact 0.4
  title 'Ensure ptrace scope is restricted'
  desc 'kernel.yama.ptrace_scope should be 1 or higher to limit process debugging.'
  tag cis: '1.5.2'
  describe kernel_parameter('kernel.yama.ptrace_scope') do
    its('value') { should cmp >= 1 }
  end
end

control 'cis-1.5.3-core-dumps' do
  impact 0.4
  title 'Ensure core dump backtraces / SUID core dumps are restricted'
  desc 'fs.suid_dumpable must be 0 so set-UID programs do not produce core dumps.'
  tag cis: '1.5.3'
  describe kernel_parameter('fs.suid_dumpable') do
    its('value') { should eq 0 }
  end
end

control 'cis-1.5.4-prelink' do
  impact 0.3
  title 'Ensure prelink is not installed'
  desc 'prelink alters binaries and can interfere with AIDE; it should not be installed.'
  tag cis: '1.5.4'
  describe package('prelink') do
    it { should_not be_installed }
  end
end

# 1.7 Command line warning banners
control 'cis-1.7.1-motd' do
  impact 0.2
  title 'Ensure local login warning banner is configured properly'
  desc '/etc/motd must not leak OS/version information via escape sequences.'
  tag cis: '1.7.1'
  describe file('/etc/motd') do
    its('content') { should_not match(/(\\v|\\r|\\m|\\s)/) }
  end
end

control 'cis-1.7.2-issue' do
  impact 0.2
  title 'Ensure /etc/issue does not reference OS version'
  desc 'The login banner must not disclose system information.'
  tag cis: '1.7.2'
  describe file('/etc/issue') do
    its('content') { should_not match(/(\\v|\\r|\\m|\\s)/) }
  end
end
