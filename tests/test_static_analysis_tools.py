"""
Tests to validate static analysis and code quality tools configuration.

This module tests that all configured static analysis tools (mypy, flake8, pylint,
black, isort, bandit) are properly configured and functioning correctly.

Tests validate:
- Tool installation and basic functionality
- Configuration file parsing
- Code analysis on sample files
- Integration between tools
"""

import subprocess
import sys
import os
from pathlib import Path


class TestStaticAnalysisTools:
    """Test static analysis tools configuration and functionality."""

    def test_black_installation_and_basic_functionality(self):
        """Test that black is installed and can format code."""
        # Check black is available
        result = subprocess.run(
            [sys.executable, "-m", "black", "--version"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0, f"Black not installed: {result.stderr}"
        assert "black" in result.stdout.lower()

    def test_black_configuration(self):
        """Test black configuration is working."""
        # Create a test file with poorly formatted code
        test_file = Path("test_black_format.py")
        test_file.write_text("""
def poorly_formatted_function(  arg1,arg2   ,   arg3):
    if arg1  ==  "test":
        result=  arg2  +  arg3
        return    result
    else:
        return   None
""")

        try:
            # Run black on the test file
            result = subprocess.run(
                [sys.executable, "-m", "black", "--check", "--diff", str(test_file)],
                capture_output=True,
                text=True
            )

            # Black should detect formatting issues
            assert result.returncode == 1, "Black should detect formatting issues"

            # Run black to format the file
            result = subprocess.run(
                [sys.executable, "-m", "black", str(test_file)],
                capture_output=True,
                text=True
            )
            assert result.returncode == 0, f"Black formatting failed: {result.stderr}"

            # Verify file was formatted
            content = test_file.read_text()
            assert "def poorly_formatted_function(" in content
            # Check that spacing was corrected
            assert "arg1,arg2" not in content

        finally:
            # Clean up
            test_file.unlink(missing_ok=True)

    def test_isort_installation_and_basic_functionality(self):
        """Test that isort is installed and can sort imports."""
        result = subprocess.run(
            [sys.executable, "-m", "isort", "--version"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0, f"isort not installed: {result.stderr}"

    def test_isort_configuration(self):
        """Test isort configuration is working."""
        # Create a test file with unsorted imports
        test_file = Path("test_isort_imports.py")
        test_file.write_text("""
import os
import sys
from pathlib import Path
import json
from typing import Dict, List
""")

        try:
            # Check if imports need sorting
            result = subprocess.run(
                [sys.executable, "-m", "isort", "--check-only", "--diff", str(test_file)],
                capture_output=True,
                text=True
            )

            # isort should process the file successfully
            assert result.returncode in [0, 1], f"isort check failed: {result.stderr}"

            # Run isort to sort imports
            result = subprocess.run(
                [sys.executable, "-m", "isort", str(test_file)],
                capture_output=True,
                text=True
            )
            assert result.returncode == 0, f"isort sorting failed: {result.stderr}"

        finally:
            # Clean up
            test_file.unlink(missing_ok=True)

    def test_flake8_installation_and_basic_functionality(self):
        """Test that flake8 is installed and can analyze code."""
        result = subprocess.run(
            [sys.executable, "-m", "flake8", "--version"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0, f"flake8 not installed: {result.stderr}"

    def test_flake8_configuration(self):
        """Test flake8 configuration is working."""
        # Create a test file with some linting issues
        test_file = Path("test_flake8_lint.py")
        test_file.write_text("""
def function_with_issues( unused_arg):
    unused_variable = 42
    if True:
        x=1+2
    return
""")

        try:
            # Run flake8 on the test file
            result = subprocess.run(
                [sys.executable, "-m", "flake8", str(test_file)],
                capture_output=True,
                text=True
            )

            # flake8 should detect issues
            assert result.returncode == 1, "flake8 should detect linting issues"

            # Check that it found expected issues
            output = result.stdout + result.stderr
            # Should detect unused variable, unused argument, etc.
            assert "unused" in output.lower() or "F401" in output or "F841" in output

        finally:
            # Clean up
            test_file.unlink(missing_ok=True)

    def test_mypy_installation_and_basic_functionality(self):
        """Test that mypy is installed and can analyze types."""
        result = subprocess.run(
            [sys.executable, "-m", "mypy", "--version"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0, f"mypy not installed: {result.stderr}"

    def test_mypy_configuration(self):
        """Test mypy configuration is working."""
        # Create a test file with type issues
        test_file = Path("test_mypy_types.py")
        test_file.write_text("""
def add_numbers(a, b):
    return a + b

result = add_numbers("hello", 42)
""")

        try:
            # Run mypy on the test file
            result = subprocess.run(
                [sys.executable, "-m", "mypy", str(test_file)],
                capture_output=True,
                text=True
            )

            # mypy should detect type issues
            assert result.returncode == 1, "mypy should detect type issues"

            # Check for type error messages
            output = result.stdout + result.stderr
            assert "error" in output.lower()

        finally:
            # Clean up
            test_file.unlink(missing_ok=True)

    def test_pylint_installation_and_basic_functionality(self):
        """Test that pylint is installed and can analyze code."""
        result = subprocess.run(
            [sys.executable, "-m", "pylint", "--version"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0, f"pylint not installed: {result.stderr}"

    def test_pylint_configuration(self):
        """Test pylint configuration is working."""
        # Create a test file with pylint issues
        test_file = Path("test_pylint_analyze.py")
        test_file.write_text("""
def badFunction():
    x=1
    y=2
    z=x+y
    return z
""")

        try:
            # Run pylint on the test file
            result = subprocess.run(
                [sys.executable, "-m", "pylint", str(test_file)],
                capture_output=True,
                text=True
            )

            # pylint should analyze the file (may return 0 or non-zero)
            assert result.returncode in [0, 1, 2, 4, 8, 16, 32], f"pylint failed: {result.stderr}"

        finally:
            # Clean up
            test_file.unlink(missing_ok=True)

    def test_bandit_installation_and_basic_functionality(self):
        """Test that bandit is installed and can scan for security issues."""
        result = subprocess.run(
            [sys.executable, "-m", "bandit", "--version"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0, f"bandit not installed: {result.stderr}"

    def test_ruff_installation_and_basic_functionality(self):
        """Test that ruff is installed and can analyze code."""
        result = subprocess.run(
            [sys.executable, "-m", "ruff", "--version"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0, f"ruff not installed: {result.stderr}"

    def test_pre_commit_installation(self):
        """Test that pre-commit is installed."""
        result = subprocess.run(
            [sys.executable, "-m", "pre_commit", "--version"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0, f"pre-commit not installed: {result.stderr}"

    def test_configuration_files_exist(self):
        """Test that all configuration files exist."""
        config_files = [
            ".mypy.ini",
            ".flake8",
            ".pre-commit-config.yaml",
            "pyproject.toml"
        ]

        for config_file in config_files:
            assert Path(config_file).exists(), f"Configuration file {config_file} does not exist"

    def test_black_pyproject_config(self):
        """Test black configuration in pyproject.toml."""
        import tomllib
        with open("pyproject.toml", "rb") as f:
            config = tomllib.load(f)

        assert "tool" in config
        assert "black" in config["tool"]
        assert config["tool"]["black"]["line-length"] == 100

    def test_isort_pyproject_config(self):
        """Test isort configuration in pyproject.toml."""
        import tomllib
        with open("pyproject.toml", "rb") as f:
            config = tomllib.load(f)

        assert "tool" in config
        assert "isort" in config["tool"]
        assert config["tool"]["isort"]["profile"] == "black"
        assert config["tool"]["isort"]["line_length"] == 100

    def test_ruff_pyproject_config(self):
        """Test ruff configuration in pyproject.toml."""
        import tomllib
        with open("pyproject.toml", "rb") as f:
            config = tomllib.load(f)

        assert "tool" in config
        assert "ruff" in config["tool"]
        assert config["tool"]["ruff"]["line-length"] == 100

    def test_pylint_pyproject_config(self):
        """Test pylint configuration in pyproject.toml."""
        import tomllib
        with open("pyproject.toml", "rb") as f:
            config = tomllib.load(f)

        assert "tool" in config
        assert "pylint" in config["tool"]
        assert "main" in config["tool"]["pylint"]

    def test_pre_commit_config_structure(self):
        """Test pre-commit configuration structure."""
        import yaml
        with open(".pre-commit-config.yaml", "r") as f:
            config = yaml.safe_load(f)

        assert "repos" in config
        assert len(config["repos"]) > 0

        # Check that all expected hooks are present
        hook_ids = []
        for repo in config["repos"]:
            if "hooks" in repo:
                hook_ids.extend([hook["id"] for hook in repo["hooks"]])

        expected_hooks = ["black", "isort", "flake8", "mypy", "bandit"]
        for expected_hook in expected_hooks:
            assert expected_hook in hook_ids, f"Hook {expected_hook} not found in pre-commit config"


class TestToolIntegration:
    """Test integration between different static analysis tools."""

    def test_black_isort_compatibility(self):
        """Test that black and isort configurations are compatible."""
        # Both should use line-length = 100
        import tomllib
        with open("pyproject.toml", "rb") as f:
            config = tomllib.load(f)

        black_length = config["tool"]["black"]["line-length"]
        isort_length = config["tool"]["isort"]["line_length"]

        assert black_length == isort_length == 100

    def test_flake8_black_compatibility(self):
        """Test that flake8 and black configurations don't conflict."""
        # flake8 max-line-length should match black line-length
        import configparser
        flake8_config = configparser.ConfigParser()
        flake8_config.read(".flake8")

        if flake8_config.has_section("flake8") and flake8_config.has_option("flake8", "max-line-length"):
            flake8_length = int(flake8_config.get("flake8", "max-line-length"))
        else:
            flake8_length = 100  # default

        import tomllib
        with open("pyproject.toml", "rb") as f:
            config = tomllib.load(f)

        black_length = config["tool"]["black"]["line-length"]

        assert flake8_length == black_length


class TestCodeQualityValidation:
    """Test that the tools can analyze the actual codebase."""

    def test_run_black_on_project(self):
        """Test running black on the project (check mode)."""
        # Run black in check mode on a few key files
        result = subprocess.run(
            [sys.executable, "-m", "black", "--check", "--diff", "src/"],
            capture_output=True,
            text=True
        )

        # Black check may pass or fail depending on current formatting
        # The important thing is that it runs without crashing
        assert result.returncode in [0, 1], f"black check failed: {result.stderr}"

    def test_run_isort_on_project(self):
        """Test running isort on the project (check mode)."""
        result = subprocess.run(
            [sys.executable, "-m", "isort", "--check-only", "--diff", "src/"],
            capture_output=True,
            text=True
        )

        # isort check may pass or fail depending on current imports
        assert result.returncode in [0, 1], f"isort check failed: {result.stderr}"

    def test_run_flake8_on_project(self):
        """Test running flake8 on the project."""
        result = subprocess.run(
            [sys.executable, "-m", "flake8", "src/"],
            capture_output=True,
            text=True
        )

        # flake8 may find issues or not - the important thing is it runs
        assert result.returncode in [0, 1], f"flake8 failed: {result.stderr}"

    def test_run_mypy_on_project(self):
        """Test running mypy on the project."""
        result = subprocess.run(
            [sys.executable, "-m", "mypy", "src/"],
            capture_output=True,
            text=True
        )

        # mypy may find type issues or not - the important thing is it runs
        assert result.returncode in [0, 1], f"mypy failed: {result.stderr}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
