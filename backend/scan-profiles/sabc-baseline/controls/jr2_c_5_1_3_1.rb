control 'JR2.C.5.1.3.1' do
  title 'Ensure cryptographic mechanisms are used to protect the integrity of audit tools.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_5_1_3_1'
  if os[:family] == 'debian'
    v_debian = command(<<-'SABC_V'.chomp)
      #!/bin/bash
      if [ -d /etc/aide/aide.conf.d ]; then
        conf_glob='/etc/aide/aide.conf /etc/aide/aide.conf.d/*'
      else
        conf_glob='/etc/aide.conf'
      fi
      for t in auditctl auditd ausearch aureport autrace augenrules; do
        p=$(command -v "$t" 2>/dev/null || echo "/usr/sbin/$t")
        grep -Ehs "^$p[[:space:]]" $conf_glob 2>/dev/null | grep -q 'sha512' || exit 1
      done
      exit 0
    SABC_V
    if v_debian.exit_status == 101
      describe 'Not applicable' do
        skip 'Not applicable on this node: the validate procedure reported its prerequisite (package/service) is absent.'
      end
    else
      describe v_debian do
        its('exit_status') { should cmp 0 }
      end
    end
  end
  if os[:family] == 'redhat'
    v_redhat = command(<<-'SABC_V'.chomp)
      #!/bin/bash
      if [ -d /etc/aide/aide.conf.d ]; then
        conf_glob='/etc/aide/aide.conf /etc/aide/aide.conf.d/*'
      else
        conf_glob='/etc/aide.conf'
      fi
      for t in auditctl auditd ausearch aureport autrace augenrules; do
        p=$(command -v "$t" 2>/dev/null || echo "/usr/sbin/$t")
        grep -Ehs "^$p[[:space:]]" $conf_glob 2>/dev/null | grep -q 'sha512' || exit 1
      done
      exit 0
    SABC_V
    if v_redhat.exit_status == 101
      describe 'Not applicable' do
        skip 'Not applicable on this node: the validate procedure reported its prerequisite (package/service) is absent.'
      end
    else
      describe v_redhat do
        its('exit_status') { should cmp 0 }
      end
    end
  end
end
