import json
import subprocess
import sys

# --- CONFIGURATION (Edit these after pulling the script) ---
ADMIN_USER = ""
ADMIN_PASS = ""
ADMIN_FULLNAME = ""
SSH_PUB_KEY = ""

def validate_config():
    """Ensures all required variables are set before execution."""
    required = {
        "ADMIN_USER": ADMIN_USER, 
        "ADMIN_PASS": ADMIN_PASS,
        "ADMIN_FULLNAME": ADMIN_FULLNAME, 
        "SSH_PUB_KEY": SSH_PUB_KEY
    }
    missing = [k for k, v in required.items() if not v or v.strip() == ""]
    if missing:
        print(f"ERROR: The following variables must be set: {', '.join(missing)}")
        sys.exit(1)
    print("  [✓] Configuration validated.")

def midclt_call(method, *args):
    """
    Local helper for TrueNAS middleware calls.
    Logs errors to stderr if the command fails for better troubleshooting.
    """
    cmd = ['midclt', 'call', method] + list(args)
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"  [X] ERROR in midclt method: {method}")
        print(f"      Return Code: {result.returncode}")
        print(f"      Error Message: {result.stderr.strip()}")
        return None
        
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        # Returns raw string if output is not JSON (e.g. simple success message)
        return result.stdout

def verify_user_setup(user_id):
    """Queries the system to confirm the user state matches our intent."""
    print(f"--- Verifying User: {ADMIN_USER} ---")
    
    # Retrieve actual state from the middleware [cite: 86]
    user_data = midclt_call('user.get_instance', str(user_id))
    
    if not user_data:
        print("  [X] Verification Failed: Could not retrieve user data.")
        return

    # Check key attributes against our desired state
    checks = {
        "Full Name": user_data.get("full_name") == ADMIN_FULLNAME,
        "SSH Key Present": SSH_PUB_KEY.strip() in user_data.get("sshpubkey", ""),
        "Admin Group": "builtin_administrators" in user_data.get("groups_names", []),
        "Sudo Group": "sudo" in user_data.get("groups_names", [])
    }

    for label, status in checks.items():
        icon = "[✓]" if status else "[X]"
        print(f"  {icon} {label}")
    
    if all(checks.values()):
        print(f"\nSUCCESS: User '{ADMIN_USER}' is fully configured and verified.")
    else:
        print("\nWARNING: Some verification checks failed. Review the output above.")

def setup_admin_user():
    """Executes user creation and system hardening."""
    validate_config()
    print(f"--- Setting up User: {ADMIN_USER} ---")
    
    # Check if user already exists [cite: 151]
    existing = midclt_call('user.query', json.dumps([["username", "=", ADMIN_USER]]))
    
    payload = {
        "username": ADMIN_USER,
        "full_name": ADMIN_FULLNAME,
        "password": ADMIN_PASS,
        "sshpubkey": SSH_PUB_KEY,
        "groups": ["builtin_administrators", "sudo"],
        "password_disabled": False,  # Enabled for Web UI access
        "group_create": True,        # Creates matching primary group
        "shell": "/usr/bin/zsh"
    }

    if existing:
        user_id = existing[0]['id']
        print(f"  [>] Updating existing user (ID: {user_id})...")
        midclt_call('user.update', str(user_id), json.dumps(payload))
    else:
        print(f"  [>] Creating new user...")
        user_id = midclt_call('user.create', json.dumps(payload))

    # HARDEN SSH: Forces key-based auth while keeping UI password active 
    print("--- Hardening SSH Service ---")
    midclt_call('service.update', 'ssh', json.dumps({
        "password_login": False, 
        "root_login": False
    }))
    midclt_call('service.restart', 'ssh')
    print("  [✓] SSH password and root login disabled.")
    
    if user_id:
        verify_user_setup(user_id)

if __name__ == "__main__":
    setup_admin_user()
