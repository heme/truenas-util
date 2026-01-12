import json
import subprocess
import sys

# --- CONFIGURATION (Edit these after pulling the script) ---
ADMIN_USER = ""
ADMIN_PASS = ""
ADMIN_FULLNAME = ""
SSH_PUB_KEY = ""

def validate_config():
    required = {
        "ADMIN_USER": ADMIN_USER,
        "ADMIN_PASS": ADMIN_PASS,
        "ADMIN_FULLNAME": ADMIN_FULLNAME,
        "SSH_PUB_KEY": SSH_PUB_KEY
    }
    missing = [k for k, v in required.items() if not v or v.strip() == ""]
    if missing:
        print(f"ERROR: Variables must be set: {', '.join(missing)}")
        sys.exit(1)
    print("  [✓] Configuration validated.")

def midclt_call(method, *args):
    """Local helper with improved error logging and JSON handling."""
    cmd = ['midclt', 'call', method] + list(args)
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"  [X] ERROR in midclt method: {method}")
        print(f"      Error Message: {result.stderr.strip()}")
        return None
        
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return result.stdout.strip()

def verify_user_setup(user_id):
    print(f"--- Verifying User: {ADMIN_USER} ---")
    user_data = midclt_call('user.get_instance', str(user_id))
    
    if not user_data:
        print("  [X] Verification Failed: Could not retrieve user data.")
        return

    checks = {
        "Full Name": user_data.get("full_name") == ADMIN_FULLNAME,
        "SSH Key Present": SSH_PUB_KEY.strip() in user_data.get("sshpubkey", ""),
        "Admin Group": any(g in user_data.get("groups_names", []) for g in ["builtin_administrators", "admin"]),
        "Sudo Group": "sudo" in user_data.get("groups_names", [])
    }

    for label, status in checks.items():
        icon = "[✓]" if status else "[X]"
        print(f"  {icon} {label}")

def setup_admin_user():
    validate_config()
    print(f"--- Setting up User: {ADMIN_USER} ---")
    
    # Resolve Group Names to IDs [cite: 112, 113]
    all_groups = midclt_call('group.query', '[]')
    group_map = {g['group']: g['id'] for g in all_groups if 'group' in g}
    
    target_names = ["builtin_administrators", "sudo"]
    group_ids = [group_map[name] for name in target_names if name in group_map]
    
    existing = midclt_call('user.query', json.dumps([["username", "=", ADMIN_USER]]))
    
    payload = {
        "username": ADMIN_USER,
        "full_name": ADMIN_FULLNAME,
        "password": ADMIN_PASS,
        "sshpubkey": SSH_PUB_KEY,
        "groups": group_ids,
        "password_disabled": False,
        "group_create": True,
        "shell": "/usr/bin/zsh"
    }

    if existing:
        user_id = existing[0]['id']
        midclt_call('user.update', str(user_id), json.dumps(payload))
    else:
        user_id = midclt_call('user.create', json.dumps(payload))

    # Hardening SSH Service using correct SCALE keys [cite: 72, 120]
    print("--- Hardening SSH Service ---")
    # Query to find the internal ID of the SSH service record
    ssh_service = midclt_call('service.query', '[["service", "=", "ssh"]]')
    if ssh_service:
        # Note: service.update usually takes the service name or ID [cite: 64]
        midclt_call('service.update', '"ssh"', json.dumps({
            "passwordauth": False, 
            "rootlogin": False
        }))
        midclt_call('service.restart', '"ssh"')
        print("  [✓] SSH password and root login disabled.")
    
    if user_id:
        verify_user_setup(user_id)

if __name__ == "__main__":
    setup_admin_user()