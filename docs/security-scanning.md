# Security Scanning Guide

This document provides comprehensive information about the security scanning infrastructure implemented for the Loist MCP Server, including setup, usage, configuration, and integration with development workflows.

## Overview

The Loist MCP Server implements a comprehensive security scanning framework that includes:

- **Bandit**: Python security vulnerability scanning
- **Safety**: Dependency vulnerability scanning
- **Custom Security Checks**: Application-specific security validation
- **Security Baseline**: Configurable thresholds and policies
- **Reporting**: Multiple output formats with executive summaries

## Architecture

### Security Scanning Components

```
Security Infrastructure
├── Bandit (Python Security)
│   ├── Static analysis for common vulnerabilities
│   ├── Configurable severity levels
│   └── Customizable rule exclusions
├── Safety (Dependencies)
│   ├── Known vulnerability database scanning
│   ├── Package dependency analysis
│   └── Automated vulnerability updates
├── Custom Checks
│   ├── Hardcoded secrets detection
│   ├── Debug code identification
│   ├── File permissions validation
│   └── Security-related TODO tracking
└── Reporting & Baseline
    ├── JSON/HTML/text report generation
    ├── Security baseline configuration
    └── CI/CD integration thresholds
```

## Quick Start

### Running Security Scans

Execute the comprehensive security scan:

```bash
# Run all security scans
./scripts/security-scan.sh

# Output includes:
# - Bandit Python security analysis
# - Safety dependency vulnerability scan
# - Custom security checks
# - Executive summary report
```

### Manual Tool Usage

Run individual security tools:

```bash
# Bandit - Python security scanning
bandit -r src/ -f json -o reports/bandit-scan.json

# Safety - Dependency vulnerability scanning
safety scan --output json --target .

# Custom checks are part of the main script
```

## Security Tools Configuration

### Bandit Configuration

Bandit is configured via the `.bandit` file in the project root:

```ini
[bandit]
# Exclude directories from scanning
exclude_dirs = ["tests", "scripts", "__pycache__", ".git"]

# Skip certain tests that are not relevant
skips = ["B101", "B601", "B404", "B603"]

# Severity levels to report (LOW, MEDIUM, HIGH)
severity = ["LOW", "MEDIUM", "HIGH"]

# Confidence levels to report (LOW, MEDIUM, HIGH)
confidence = ["LOW", "MEDIUM", "HIGH"]

# Output format (txt, json, xml, html, screen)
format = json
```

### Safety Configuration

Safety is configured in `pyproject.toml`:

```toml
[tool.safety]
# Safety configuration for dependency vulnerability scanning
# Scans against Safety DB for known vulnerabilities in dependencies
```

### Security Baseline

The security baseline is defined in `security-baseline.json`:

```json
{
  "name": "Loist MCP Server Security Baseline",
  "version": "1.0.0",
  "policies": {
    "bandit": {
      "acceptableThresholds": {
        "highSeverity": 0,
        "mediumSeverity": 5,
        "lowSeverity": 20
      }
    },
    "safety": {
      "acceptableThresholds": {
        "criticalVulnerabilities": 0,
        "highVulnerabilities": 0,
        "mediumVulnerabilities": 3
      }
    }
  }
}
```

## Security Scan Output

### Report Structure

Security scans generate timestamped reports in `reports/` directory:

```
reports/
├── bandit-scan-20251105-145300.json     # Bandit detailed results
├── bandit-scan-20251105-145300.html     # Bandit HTML report
├── safety-scan-20251105-145300.json     # Safety vulnerability data
├── custom-security-checks-20251105-145300.txt  # Custom checks
└── security-scan-summary-20251105-145300.txt   # Executive summary
```

### Executive Summary Format

The summary report provides key metrics and recommendations:

```
Security Scan Summary Report
Generated: 2025-11-05 14:53:00
=================================

🔍 Scan Overview:
  - Bandit (Python Security): ✅ Completed
  - Safety (Dependencies): ✅ Completed
  - Custom Checks: ✅ Completed

📊 Key Metrics:
  - High Severity Issues (Bandit): 0
  - Dependency Vulnerabilities: 0

📂 Detailed Reports:
  - Bandit JSON: reports/bandit-scan-20251105-145300.json
  - Bandit HTML: reports/bandit-scan-20251105-145300.html
  - Safety: reports/safety-scan-20251105-145300.json
  - Custom Checks: reports/custom-security-checks-20251105-145300.txt

💡 Recommendations:
  - Review high-severity issues found by Bandit
  - Address dependency vulnerabilities identified by Safety
  - Review custom security checks for additional issues
  - Consider integrating these scans into CI/CD pipeline
```

## Security Policies

### Acceptable Thresholds

| Tool | High Severity | Medium Severity | Low Severity |
|------|---------------|-----------------|--------------|
| Bandit | 0 (Zero tolerance) | 5 | 20 |
| Safety | 0 (Zero tolerance) | 3 | 10 |

### Blocked Vulnerability Categories

The following Bandit vulnerability categories are considered critical and must be addressed:

- `B102`: Use of exec
- `B103`: Use of setuid/setgid
- `B104`: Use of hardcoded bind to all interfaces
- `B105-B108`: Use of hardcoded passwords
- `B301-B306`: Use of insecure deserialization/serialization
- `B401`: Use of telnetlib
- `B501-B507`: SSL/TLS configuration issues
- `B601-B607`: Subprocess security issues

## Custom Security Checks

### Hardcoded Secrets Detection

Scans for potential hardcoded secrets in source code:

```python
# ❌ Detected patterns:
PASSWORD = "secret123"
API_KEY = "sk-1234567890"
TOKEN = "token_value"
```

### Debug Code Identification

Identifies debug code that should be removed from production:

```python
# ❌ Detected patterns:
print("Debug output")          # Print statements
import pdb; pdb.set_trace()    # Python debugger
console.log("Debug")           # JavaScript console (if applicable)
```

### File Permissions Validation

Ensures Python files are not executable:

```bash
# ✅ Good: Standard file permissions
-rw-r--r-- 1 user group 1024 Nov 5 14:53 script.py

# ❌ Bad: Executable Python files
-rwxr-xr-x 1 user group 1024 Nov 5 14:53 script.py
```

### Security TODO Tracking

Identifies security-related TODO comments:

```python
# ❌ Detected patterns:
# TODO: Implement proper authentication
# TODO: Add input validation
# TODO: Fix security vulnerability
```

## CI/CD Integration

### Automated Security Gates

Configure security scanning in CI/CD pipelines:

```yaml
# .github/workflows/security-scan.yml
name: Security Scan
on: [push, pull_request]

jobs:
  security:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run Security Scan
        run: ./scripts/security-scan.sh
      - name: Upload Security Reports
        uses: actions/upload-artifact@v4
        with:
          name: security-reports
          path: reports/
```

### Failure Thresholds

Configure pipeline to fail on security issues:

```bash
#!/bin/bash
# security-gate.sh

# Run security scan
./scripts/security-scan.sh

# Check for critical issues
if [ $(jq '.metrics._totals."SEVERITY.HIGH"' reports/bandit-scan-*.json) -gt 0 ]; then
    echo "❌ High-severity security issues found"
    exit 1
fi

echo "✅ Security scan passed"
```

## Development Workflow Integration

### Pre-Commit Hooks

Integrate security scanning into pre-commit hooks:

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: security-scan
        name: Security Scan
        entry: ./scripts/security-scan.sh
        language: system
        pass_filenames: false
        files: ^(src/|scripts/|pyproject.toml)$
```

### IDE Integration

Configure VS Code for security scanning:

```json
// .vscode/settings.json
{
  "python.linting.banditEnabled": true,
  "python.linting.banditArgs": [
    "--configfile", ".bandit"
  ]
}
```

## Troubleshooting

### Common Issues

#### Safety Network Issues

**Problem:** Safety scan fails with network errors
**Solution:** Safety requires internet access to check vulnerability databases

```bash
# Check network connectivity
curl -s https://pypi.org/ > /dev/null && echo "Network OK" || echo "Network issue"

# Run with offline mode (limited functionality)
safety scan --offline-only --target .
```

#### Bandit False Positives

**Problem:** Bandit reports false positive vulnerabilities
**Solution:** Configure skips in `.bandit` file

```ini
# .bandit
skips = ["B101", "B404", "B603"]
```

#### Report Generation Failures

**Problem:** Security scan completes but reports aren't generated
**Solution:** Check file permissions and jq availability

```bash
# Ensure reports directory exists and is writable
mkdir -p reports
chmod 755 reports

# Verify jq is installed
which jq || echo "jq not found - install jq for JSON processing"
```

### Performance Optimization

#### Large Codebases

For large codebases, optimize Bandit performance:

```bash
# Use parallel processing
bandit -r src/ -f json -o report.json --processes 4

# Scan specific directories
bandit -r src/core src/api -f json -o report.json

# Exclude heavy directories
bandit -r src/ -f json -o report.json --exclude "src/tests/*,src/docs/*"
```

#### CI/CD Performance

Optimize for CI/CD environments:

```yaml
jobs:
  security:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Security Scan
        run: |
          ./scripts/security-scan.sh
        timeout-minutes: 10
      - name: Upload Reports
        uses: actions/upload-artifact@v4
        with:
          name: security-reports
          path: reports/
```

## Security Baseline Management

### Updating Thresholds

Update security baseline as project matures:

```json
{
  "policies": {
    "bandit": {
      "acceptableThresholds": {
        "highSeverity": 0,
        "mediumSeverity": 2,  // Tightened from 5
        "lowSeverity": 15     // Tightened from 20
      }
    }
  }
}
```

### Adding New Rules

Extend custom security checks:

```bash
# custom-security-checks.sh
#!/bin/bash

# Add new security checks
echo "🔍 Checking for insecure logging..."
grep -r "logger.*password\|log.*secret" src/ && echo "⚠️  Sensitive data logging detected"

echo "🔍 Checking for unsafe YAML loading..."
grep -r "yaml\..*load" src/ && echo "⚠️  Unsafe YAML loading detected"
```

## Integration with Task Management

### Security in Development Workflow

Security scanning integrates with Task Master workflow:

1. **Task Implementation**: Run security scans during development
2. **Code Review**: Include security scan results in PR reviews
3. **Task Completion**: Verify security baseline before marking tasks done
4. **Regression Testing**: Automated security scans on task completion

### Task-Specific Security Checks

```bash
# Run security scan for specific task
./scripts/security-scan.sh

# Check results for task-related files
grep "task-16" reports/security-scan-summary-*.txt
```

## Best Practices

### Security-First Development

1. **Scan Early**: Run security scans during development, not just CI/CD
2. **Address Issues Immediately**: Fix high-severity issues before committing
3. **Baseline Maintenance**: Regularly update security baseline as project evolves
4. **Documentation**: Keep security documentation current with implementation

### Security Awareness

1. **Team Training**: Ensure team understands security tool outputs
2. **False Positive Management**: Document legitimate exceptions to security rules
3. **Vulnerability Tracking**: Monitor new vulnerability disclosures
4. **Compliance**: Align security practices with organizational policies

## References

- [Bandit Documentation](https://bandit.readthedocs.io/)
- [Safety Documentation](https://github.com/pyupio/safety)
- [OWASP Security Practices](https://owasp.org/www-project-top-ten/)
- [Python Security Best Practices](https://bestpractices.coreinfrastructure.org/en/projects/2234)

## Support

For security scanning issues or questions:

1. Check the troubleshooting section above
2. Review generated security reports in `reports/` directory
3. Consult team security guidelines
4. Open an issue with security scan outputs

---

**Last Updated**: 2025-11-05
**Security Baseline Version**: 1.0.0
**Tools Versions**: Bandit 1.8.6, Safety 3.6.2
