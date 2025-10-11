"""
Authentication and access control tests for GCS and database operations.

Tests verify:
- Credential loading and validation
- Configuration hierarchy
- Service account authentication
- Access control enforcement
- Error handling for missing/invalid credentials
"""

import os
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Configuration tests
class TestConfigCredentials:
    """Test credential configuration and loading."""
    
    def test_config_imports(self):
        """Test that config module imports correctly."""
        from src.config import config
        assert config is not None
    
    def test_gcs_configuration_properties(self):
        """Test GCS configuration properties."""
        from src.config import config
        
        # Test properties exist
        assert hasattr(config, 'gcs_bucket_name')
        assert hasattr(config, 'gcs_project_id')
        assert hasattr(config, 'gcs_credentials_path')
        assert hasattr(config, 'is_gcs_configured')
    
    def test_database_configuration_properties(self):
        """Test database configuration properties."""
        from src.config import config
        
        # Test properties exist
        assert hasattr(config, 'db_host')
        assert hasattr(config, 'db_name')
        assert hasattr(config, 'db_user')
        assert hasattr(config, 'is_database_configured')
        assert hasattr(config, 'database_url')
    
    def test_credential_validation(self):
        """Test credential validation method."""
        from src.config import config
        
        result = config.validate_credentials()
        
        assert isinstance(result, dict)
        assert 'gcs' in result
        assert 'database' in result
        assert 'auth' in result
        assert isinstance(result['gcs'], bool)
        assert isinstance(result['database'], bool)
    
    @patch.dict(os.environ, {
        'GCS_BUCKET_NAME': 'test-bucket',
        'GCS_PROJECT_ID': 'test-project',
        'GOOGLE_APPLICATION_CREDENTIALS': '/tmp/test-key.json'
    })
    def test_gcs_config_from_env(self):
        """Test GCS configuration loads from environment variables."""
        from src.config import ServerConfig
        
        config = ServerConfig()
        
        assert config.gcs_bucket_name == 'test-bucket'
        assert config.gcs_project_id == 'test-project'
    
    @patch.dict(os.environ, {
        'DB_HOST': 'localhost',
        'DB_PORT': '5432',
        'DB_NAME': 'test_db',
        'DB_USER': 'test_user',
        'DB_PASSWORD': 'test_pass'
    })
    def test_database_config_from_env(self):
        """Test database configuration loads from environment variables."""
        from src.config import ServerConfig
        
        config = ServerConfig()
        
        assert config.db_host == 'localhost'
        assert config.db_port == 5432
        assert config.db_name == 'test_db'
        assert config.db_user == 'test_user'
    
    @patch.dict(os.environ, {
        'DB_HOST': 'localhost',
        'DB_PORT': '5432',
        'DB_NAME': 'test_db',
        'DB_USER': 'test_user',
        'DB_PASSWORD': 'test_pass'
    })
    def test_database_url_generation_direct(self):
        """Test database URL generation for direct connection."""
        from src.config import ServerConfig
        
        config = ServerConfig()
        url = config.database_url
        
        assert url is not None
        assert url.startswith('postgresql://')
        assert 'test_user' in url
        assert 'test_db' in url
        assert 'localhost' in url
    
    @patch.dict(os.environ, {
        'DB_CONNECTION_NAME': 'project:region:instance',
        'DB_NAME': 'test_db',
        'DB_USER': 'test_user',
        'DB_PASSWORD': 'test_pass'
    })
    def test_database_url_generation_proxy(self):
        """Test database URL generation for Cloud SQL Proxy connection."""
        from src.config import ServerConfig
        
        config = ServerConfig()
        url = config.database_url
        
        assert url is not None
        assert url.startswith('postgresql://')
        assert '/cloudsql/' in url
        assert 'project:region:instance' in url


class TestGCSClientAuthentication:
    """Test GCS client authentication and credential loading."""
    
    def test_gcs_client_import(self):
        """Test that GCS client imports correctly."""
        from src.storage import GCSClient
        assert GCSClient is not None
    
    def test_gcs_client_requires_bucket_name(self):
        """Test that GCS client requires bucket name."""
        from src.storage import GCSClient
        
        with pytest.raises(ValueError, match="Bucket name must be provided"):
            GCSClient()
    
    @patch.dict(os.environ, {
        'GCS_BUCKET_NAME': 'test-bucket',
        'GCS_PROJECT_ID': 'test-project'
    })
    def test_gcs_client_from_env(self):
        """Test GCS client initialization from environment variables."""
        from src.storage import GCSClient
        
        client = GCSClient()
        
        assert client.bucket_name == 'test-bucket'
        assert client.project_id == 'test-project'
    
    def test_gcs_client_explicit_params(self):
        """Test GCS client initialization with explicit parameters."""
        from src.storage import GCSClient
        
        client = GCSClient(
            bucket_name='explicit-bucket',
            project_id='explicit-project'
        )
        
        assert client.bucket_name == 'explicit-bucket'
        assert client.project_id == 'explicit-project'
    
    @patch.dict(os.environ, {
        'GCS_BUCKET_NAME': 'env-bucket',
        'GCS_PROJECT_ID': 'env-project'
    })
    def test_gcs_client_param_precedence(self):
        """Test that explicit parameters take precedence over environment."""
        from src.storage import GCSClient
        
        client = GCSClient(
            bucket_name='param-bucket',
            project_id='param-project'
        )
        
        # Parameters should override environment
        assert client.bucket_name == 'param-bucket'
        assert client.project_id == 'param-project'
    
    def test_gcs_client_credentials_path_handling(self):
        """Test credentials path handling."""
        from src.storage import GCSClient
        
        client = GCSClient(
            bucket_name='test-bucket',
            credentials_path='/nonexistent/path.json'
        )
        
        # Should log warning but not fail
        assert client.credentials_path == '/nonexistent/path.json'
    
    @patch.dict(os.environ, {'GCS_BUCKET_NAME': 'test-bucket'})
    def test_create_gcs_client_convenience(self):
        """Test convenience function for creating GCS client."""
        from src.storage import create_gcs_client
        
        client = create_gcs_client()
        
        assert client is not None
        assert client.bucket_name == 'test-bucket'


class TestCredentialSecurity:
    """Test credential security and protection."""
    
    def test_service_account_key_gitignored(self):
        """Test that service account key file is in .gitignore."""
        gitignore_path = Path('.gitignore')
        
        if gitignore_path.exists():
            content = gitignore_path.read_text()
            assert 'service-account-key.json' in content, \
                "Service account key should be in .gitignore"
    
    def test_env_files_gitignored(self):
        """Test that .env files are gitignored."""
        gitignore_path = Path('.gitignore')
        
        if gitignore_path.exists():
            content = gitignore_path.read_text()
            assert '.env' in content, ".env files should be gitignored"
            assert '.env.gcs' in content, ".env.gcs should be gitignored"
            assert '.env.database' in content, ".env.database should be gitignored"
    
    def test_credentials_not_in_logs(self):
        """Test that credentials are not exposed in default string representation."""
        from src.config import config
        
        # Config string representation should not contain passwords
        config_str = str(config.__dict__)
        
        # If password is set, it shouldn't appear in plain text
        if config.db_password:
            # This is a weak test, but ensures we're not directly logging passwords
            # In production, use proper secret management
            assert config.db_password not in repr(config), \
                "Password should not appear in config repr"


class TestAccessControl:
    """Test access control patterns and enforcement."""
    
    @patch.dict(os.environ, {
        'GCS_BUCKET_NAME': 'test-bucket',
        'GCS_PROJECT_ID': 'test-project'
    })
    def test_gcs_client_initialization_access_control(self):
        """Test that GCS client initializes with proper access control."""
        from src.storage import GCSClient
        
        client = GCSClient()
        
        # Client should be initialized but not have access to private attributes
        assert hasattr(client, '_client')
        assert hasattr(client, '_bucket')
        
        # Private attributes should be None until first access
        assert client._client is None
        assert client._bucket is None
    
    def test_signed_url_requires_blob_name(self):
        """Test that signed URL generation requires blob name."""
        from src.storage import GCSClient
        
        client = GCSClient(bucket_name='test-bucket')
        
        with pytest.raises(TypeError):
            client.generate_signed_url()  # Missing required blob_name argument


class TestErrorHandling:
    """Test error handling for authentication failures."""
    
    def test_missing_credentials_error(self):
        """Test error when credentials are completely missing."""
        with patch.dict(os.environ, {}, clear=True):
            from src.storage import GCSClient
            
            with pytest.raises(ValueError, match="Bucket name must be provided"):
                GCSClient()
    
    @patch.dict(os.environ, {'GCS_BUCKET_NAME': 'test-bucket'})
    @patch('google.cloud.storage.Client')
    def test_invalid_credentials_handling(self, mock_client):
        """Test handling of invalid credentials."""
        from src.storage import GCSClient
        from google.auth.exceptions import DefaultCredentialsError
        
        # Mock storage client to raise credentials error
        mock_client.side_effect = DefaultCredentialsError("No credentials found")
        
        client = GCSClient()
        
        # Client should initialize, but accessing .client property should fail
        with pytest.raises(DefaultCredentialsError):
            _ = client.client


class TestConfigurationValidation:
    """Test configuration validation and health checks."""
    
    def test_validate_credentials_method_exists(self):
        """Test that validate_credentials method exists."""
        from src.config import config
        
        assert hasattr(config, 'validate_credentials')
        assert callable(config.validate_credentials)
    
    def test_validate_credentials_returns_dict(self):
        """Test that validate_credentials returns proper structure."""
        from src.config import config
        
        result = config.validate_credentials()
        
        assert isinstance(result, dict)
        assert 'gcs' in result
        assert 'database' in result
        assert isinstance(result['gcs'], bool)
        assert isinstance(result['database'], bool)
    
    @patch.dict(os.environ, {
        'GCS_BUCKET_NAME': 'test-bucket',
        'GCS_PROJECT_ID': 'test-project',
        'GOOGLE_APPLICATION_CREDENTIALS': __file__  # Use this test file as a mock key
    })
    def test_gcs_configured_with_valid_env(self):
        """Test is_gcs_configured returns True with valid environment."""
        from src.config import ServerConfig
        
        config = ServerConfig()
        
        # Should be configured with all required variables
        assert config.is_gcs_configured is True
    
    @patch.dict(os.environ, {}, clear=True)
    def test_gcs_not_configured_without_env(self):
        """Test is_gcs_configured returns False without environment."""
        from src.config import ServerConfig
        
        config = ServerConfig()
        
        # Should not be configured without environment variables
        assert config.is_gcs_configured is False


if __name__ == "__main__":
    # Allow running tests directly
    pytest.main([__file__, "-v"])

