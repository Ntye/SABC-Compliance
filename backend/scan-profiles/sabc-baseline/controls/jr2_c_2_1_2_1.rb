control 'JR2.C.2.1.2.1' do
  title 'Ensure chrony is running as user _chrony.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_2_1_2_1'
  if os.debian?
    v_debian = command(<<-'SABC_V'.chomp)
      ps -ef | awk '(/[c]hronyd/ && $1!="_chrony") { print $1 }'
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
  if os.redhat?
    v_redhat = command(<<-'SABC_V'.chomp)
      grep -Psi -- '^\h*OPTIONS=\"?\h*([^#\n\r]+\h+)?-u\h+root\b'
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
