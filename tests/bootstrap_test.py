import pytest
import json
from unittest.mock import patch, MagicMock
from scripts.bootstrap import validate_config, midclt_call, setup_admin_user

# 1. Test Configuration Validation
def test_validate_config_fails_when_empty():
    """Ensures script exits if variables are not set[cite: 38]."""
    with patch('scripts.bootstrap.ADMIN_USER', ''):
        with pytest.raises(SystemExit):
            validate_config()

# 2. Test Middleware Helper Logic
@patch('subprocess.run')
def test_midclt_call_success(mock_run):
    """Simulates a successful JSON response from TrueNAS."""
    mock_run.return_value.returncode = 0
    mock_run.return_value.stdout = json.dumps({"id": 1})
    
    result = midclt_call('user.create', '{"payload": "data"}')
    assert result == {"id": 1}  # [cite: 33]

@patch('subprocess.run')
def test_midclt_call_error_logging(mock_run, capsys):
    """Verifies that errors are captured and printed[cite: 86, 87]."""
    mock_run.return_value.returncode = 1
    mock_run.return_value.stderr = "Internal Server Error"
    
    result = midclt_call('user.create', '{}')
    
    captured = capsys.readouterr()
    assert result is None
    assert "[X] ERROR in midclt method" in captured.out  # [cite: 87]

# 3. Test User Setup Logic (Mocking the middleware response)
@patch('scripts.bootstrap.midclt_call')
@patch('scripts.bootstrap.validate_config')
def test_setup_admin_user_new(mock_validate, mock_midclt):
    """Tests the flow for creating a brand new user[cite: 148, 151]."""
    # Mock user.query to return empty (user doesn't exist)
    # Mock user.create to return a new ID
    # Mock service updates
    mock_midclt.side_effect = [
        [],        # user.query result
        10,        # user.create result (ID 10)
        {},        # service.update (ssh)
        True,      # service.restart (ssh)
        {"id": 10, "username": "admin", "groups_names": ["builtin_administrators", "sudo"]} # verify_user_setup
    ]
    
    # We don't want the script to actually fail if the config is empty during tests
    mock_validate.return_value = True 
    
    # This just ensures the function executes without unhandled exceptions
    setup_admin_user() 
    assert mock_midclt.called  # [cite: 151]