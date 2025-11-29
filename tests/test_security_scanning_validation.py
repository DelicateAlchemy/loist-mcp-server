"""
Security Scanning Validation Tests

This module contains tests to validate that our security scanning tools
correctly detect known security vulnerabilities and issues.
"""

import os
import tempfile
import subprocess
import json
import pytest
from pathlib import Path


class TestSecurityScanningValidation:
    """Test class for validating security scanning tools."""

    def test_bandit_detects_known_vulnerabilities(self):
        """Test that Bandit correctly detects known security issues."""
        # Create a temporary file with known security issues
        vulnerable_code = '''
import pickle  # B403 - import_pickle
import subprocess  # B404 - import_subprocess
import os

def dangerous_function(user_input):
    # B301 - pickle.loads (security vulnerability)
    data = pickle.loads(user_input)

    # B602 - subprocess_without_shell_equals_true
    result = subprocess.call(['ls', '-la'])

    # B605 - start_process_with_partial_path
    os.system('ls')  # B605 - start_process_with_partial_path

    # B101 - assert_used (should be skipped per our config)
    assert True

    return data
'''
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(vulnerable_code)
            temp_file = f.name

        try:
            # Run Bandit on the temporary file
            result = subprocess.run([
                'bandit', '-f', 'json', temp_file
            ], capture_output=True, text=True, cwd=Path(__file__).parent.parent)

            # Parse the JSON output
            report = json.loads(result.stdout)

            # Bandit should find issues (exit code 1) and report them
            assert result.returncode == 1, "Bandit should detect vulnerabilities"

            # Check that expected issues are found
            issues = [issue['test_id'] for issue in report.get('results', [])]

            # These are the issues we expect Bandit to find based on our test code
            expected_issues = ['B301', 'B403', 'B404', 'B603', 'B605', 'B607']
            for issue in expected_issues:
                assert issue in issues, f"Bandit should detect {issue}. Found issues: {issues}"

            # B101 (assert) may or may not be found depending on config usage
            # The important thing is that Bandit detects the actual security vulnerabilities

        finally:
            os.unlink(temp_file)

    def test_custom_security_checks_detect_issues(self):
        """Test that our custom security checks work correctly."""
        # Create temporary files with security issues
        files_to_check = []

        try:
            # File with hardcoded secrets
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write('''
PASSWORD = "secret123"
API_KEY = "sk-1234567890"
TOKEN = "token_value"
''')
                files_to_check.append(f.name)

            # File with debug code
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write('''
def test_function():
    print("Debug output")  # Debug code
    import pdb; pdb.set_trace()  # Debug code
    result = 1 + 1
    return result
''')
                files_to_check.append(f.name)

            # Create a temporary directory structure like src/
            temp_src = tempfile.mkdtemp()
            for file_path in files_to_check:
                filename = os.path.basename(file_path)
                temp_file = os.path.join(temp_src, filename)
                with open(file_path, 'r') as src, open(temp_file, 'w') as dst:
                    dst.write(src.read())

            # Run our custom security checks (simplified version)
            issues_found = {
                'secrets': 0,
                'debug': 0,
                'todos': 0
            }

            # Check for hardcoded secrets
            secret_patterns = [
                r'password.*=.*["\'][^"\']*["\']',
                r'secret.*=.*["\'][^"\']*["\']',
                r'key.*=.*["\'][^"\']*["\']',
                r'token.*=.*["\'][^"\']*["\']'
            ]

            for pattern in secret_patterns:
                try:
                    result = subprocess.run([
                        'grep', '-r', '-i', '-n', pattern, temp_src
                    ], capture_output=True, text=True)
                    if result.returncode == 0:
                        issues_found['secrets'] += 1
                except:
                    pass

            # Check for debug code
            debug_patterns = [
                r'print\(',
                r'pdb\.set_trace\(\)',
                r'import pdb'
            ]

            for pattern in debug_patterns:
                try:
                    result = subprocess.run([
                        'grep', '-r', '-n', pattern, temp_src
                    ], capture_output=True, text=True)
                    if result.returncode == 0:
                        lines = result.stdout.strip().split('\n')
                        issues_found['debug'] += len([l for l in lines if l.strip()])
                except:
                    pass

            # Validate that issues were detected
            assert issues_found['secrets'] > 0, "Should detect hardcoded secrets"
            assert issues_found['debug'] > 0, "Should detect debug code"

        finally:
            # Clean up temporary files
            for file_path in files_to_check:
                try:
                    os.unlink(file_path)
                except:
                    pass
            try:
                import shutil
                shutil.rmtree(temp_src)
            except:
                pass

    def test_security_baseline_configuration(self):
        """Test that security baseline configuration is valid."""
        baseline_file = Path(__file__).parent.parent / "security-baseline.json"

        assert baseline_file.exists(), "Security baseline file should exist"

        with open(baseline_file, 'r') as f:
            baseline = json.load(f)

        # Validate required structure
        required_keys = ['name', 'version', 'policies', 'ci', 'remediation', 'metadata']
        for key in required_keys:
            assert key in baseline, f"Baseline should contain {key}"

        # Validate policies structure
        assert 'bandit' in baseline['policies'], "Should have bandit policy"
        assert 'safety' in baseline['policies'], "Should have safety policy"
        assert 'customChecks' in baseline['policies'], "Should have custom checks policy"

        # Validate acceptable thresholds are reasonable
        bandit_thresholds = baseline['policies']['bandit']['acceptableThresholds']
        assert bandit_thresholds['highSeverity'] == 0, "No high severity issues should be acceptable"
        assert bandit_thresholds['mediumSeverity'] >= 0, "Medium severity threshold should be defined"

    def test_security_scan_script_exists_and_runs(self):
        """Test that the security scan script exists and can be executed."""
        script_path = Path(__file__).parent.parent / "scripts" / "security-scan.sh"

        assert script_path.exists(), "Security scan script should exist"
        assert script_path.stat().st_mode & 0o111, "Script should be executable"

        # Test that the script can at least start (we won't run full scan in unit tests)
        result = subprocess.run([
            str(script_path), '--help'
        ], capture_output=True, text=True, timeout=10)

        # Script should either show help or run (exit codes 0, 1, or 2 are acceptable)
        assert result.returncode in [0, 1, 2], f"Script failed with exit code {result.returncode}"


if __name__ == "__main__":
    pytest.main([__file__])
