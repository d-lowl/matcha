"""Tests for the Pulumi service."""
import os
import tempfile
import unittest.mock
from pathlib import Path

import pytest

from matcha_ml.services.pulumi_service import (
    PulumiConfig,
    PulumiResult,
    PulumiService,
)


class TestPulumiConfig:
    """Test PulumiConfig class."""

    def test_default_config(self):
        """Test default configuration values."""
        config = PulumiConfig()
        
        expected_working_dir = os.path.join(
            os.getcwd(), ".matcha", "infrastructure", "pulumi"
        )
        
        assert config.working_dir == expected_working_dir
        assert config.capture_output is True
        assert config.stack_name == "dev"
        assert config.component == "default"

    def test_custom_config(self):
        """Test custom configuration values."""
        config = PulumiConfig(
            working_dir="/custom/path",
            capture_output=False,
            stack_name="production",
            component="llm"
        )
        
        assert config.working_dir == "/custom/path"
        assert config.capture_output is False
        assert config.stack_name == "production"
        assert config.component == "llm"


class TestPulumiResult:
    """Test PulumiResult class."""

    def test_pulumi_result_creation(self):
        """Test PulumiResult creation."""
        result = PulumiResult(
            return_code=0,
            std_out="Success",
            std_err=""
        )
        
        assert result.return_code == 0
        assert result.std_out == "Success"
        assert result.std_err == ""


class TestPulumiService:
    """Test PulumiService class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.config = PulumiConfig()
        self.service = PulumiService(self.config)

    def test_service_initialization(self):
        """Test service initialization."""
        assert self.service.config == self.config

    @unittest.mock.patch("subprocess.run")
    def test_check_installation_success(self, mock_run):
        """Test successful Pulumi installation check."""
        # Mock successful version command
        mock_run.return_value.returncode = 0
        
        result = self.service.check_installation()
        
        assert result is True
        mock_run.assert_called_once_with(
            ["pulumi", "version"],
            capture_output=True,
            text=True
        )

    @unittest.mock.patch("subprocess.run")
    def test_check_installation_failure(self, mock_run):
        """Test failed Pulumi installation check."""
        # Mock FileNotFoundError
        mock_run.side_effect = FileNotFoundError()
        
        result = self.service.check_installation()
        
        assert result is False

    def test_verify_kubectl_config_file_exists(self):
        """Test kubectl config file verification when file exists."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = os.path.join(temp_dir, ".kube", "config")
            os.makedirs(os.path.dirname(config_path))
            
            # Create the config file
            with open(config_path, "w") as f:
                f.write("test config")
            
            # Mock home directory
            with unittest.mock.patch("os.path.expanduser") as mock_expand:
                mock_expand.return_value = temp_dir
                
                # Should not raise any errors
                self.service.verify_kubectl_config_file()
                
                # File should still exist
                assert os.path.exists(config_path)

    def test_verify_kubectl_config_file_creates_missing(self):
        """Test kubectl config file creation when missing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = os.path.join(temp_dir, ".kube", "config")
            
            # Mock home directory
            with unittest.mock.patch("os.path.expanduser") as mock_expand:
                mock_expand.return_value = temp_dir
                
                # File shouldn't exist initially
                assert not os.path.exists(config_path)
                
                self.service.verify_kubectl_config_file()
                
                # File should be created
                assert os.path.exists(config_path)

    def test_check_matcha_directory_exists_true(self):
        """Test matcha directory existence check when directory exists."""
        with tempfile.TemporaryDirectory() as temp_dir:
            matcha_dir = os.path.join(temp_dir, ".matcha")
            os.makedirs(matcha_dir)
            
            with unittest.mock.patch("os.getcwd") as mock_getcwd:
                mock_getcwd.return_value = temp_dir
                
                result = self.service.check_matcha_directory_exists()
                assert result is True

    def test_check_matcha_directory_exists_false(self):
        """Test matcha directory existence check when directory doesn't exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with unittest.mock.patch("os.getcwd") as mock_getcwd:
                mock_getcwd.return_value = temp_dir
                
                result = self.service.check_matcha_directory_exists()
                assert result is False

    def test_check_matcha_directory_integrity_true(self):
        """Test matcha directory integrity check when directory has contents."""
        with tempfile.TemporaryDirectory() as temp_dir:
            matcha_dir = os.path.join(temp_dir, ".matcha")
            os.makedirs(matcha_dir)
            
            # Create a file in the directory
            test_file = os.path.join(matcha_dir, "test.txt")
            with open(test_file, "w") as f:
                f.write("test content")
            
            with unittest.mock.patch("os.getcwd") as mock_getcwd:
                mock_getcwd.return_value = temp_dir
                
                result = self.service.check_matcha_directory_integrity()
                assert result is True

    def test_check_matcha_directory_integrity_false_empty(self):
        """Test matcha directory integrity check when directory is empty."""
        with tempfile.TemporaryDirectory() as temp_dir:
            matcha_dir = os.path.join(temp_dir, ".matcha")
            os.makedirs(matcha_dir)
            
            with unittest.mock.patch("os.getcwd") as mock_getcwd:
                mock_getcwd.return_value = temp_dir
                
                result = self.service.check_matcha_directory_integrity()
                assert result is False

    def test_check_matcha_directory_integrity_false_missing(self):
        """Test matcha directory integrity check when directory doesn't exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with unittest.mock.patch("os.getcwd") as mock_getcwd:
                mock_getcwd.return_value = temp_dir
                
                result = self.service.check_matcha_directory_integrity()
                assert result is False

    def test_validate_config_true(self):
        """Test config validation when Pulumi.yaml exists."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create Pulumi.yaml file
            pulumi_yaml = os.path.join(temp_dir, "Pulumi.yaml")
            with open(pulumi_yaml, "w") as f:
                f.write("name: test\nruntime: python")
            
            config = PulumiConfig(working_dir=temp_dir)
            service = PulumiService(config)
            
            result = service.validate_config()
            assert result is True

    def test_validate_config_false(self):
        """Test config validation when Pulumi.yaml doesn't exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = PulumiConfig(working_dir=temp_dir)
            service = PulumiService(config)
            
            result = service.validate_config()
            assert result is False

    def test_get_pulumi_state_dir(self):
        """Test getting Pulumi state directory path."""
        expected_path = Path(os.path.join(self.config.working_dir, ".pulumi"))
        result = self.service.get_pulumi_state_dir()
        
        assert result == expected_path

    @unittest.mock.patch("subprocess.run")
    def test_run_pulumi_command_success(self, mock_run):
        """Test successful Pulumi command execution."""
        # Mock successful command
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "Success output"
        mock_run.return_value.stderr = ""
        
        result = self.service._run_pulumi_command(["pulumi", "version"])
        
        assert result.return_code == 0
        assert result.std_out == "Success output"
        assert result.std_err == ""

    @unittest.mock.patch("subprocess.run")
    def test_run_pulumi_command_failure(self, mock_run):
        """Test failed Pulumi command execution."""
        # Mock failed command
        mock_run.return_value.returncode = 1
        mock_run.return_value.stdout = ""
        mock_run.return_value.stderr = "Error message"
        
        result = self.service._run_pulumi_command(["pulumi", "version"])
        
        assert result.return_code == 1
        assert result.std_out == ""
        assert result.std_err == "Error message"

    @unittest.mock.patch("subprocess.run")
    def test_run_pulumi_command_not_found(self, mock_run):
        """Test Pulumi command not found."""
        # Mock FileNotFoundError
        mock_run.side_effect = FileNotFoundError("pulumi not found")
        
        result = self.service._run_pulumi_command(["pulumi", "version"])
        
        assert result.return_code == 1
        assert result.std_out == ""
        assert "Pulumi command not found" in result.std_err

    @unittest.mock.patch.object(PulumiService, "_run_pulumi_command")
    def test_stack_init(self, mock_run_command):
        """Test stack initialization."""
        mock_run_command.return_value = PulumiResult(0, "Stack created", "")
        
        result = self.service.stack_init()
        
        mock_run_command.assert_called_once_with(
            ["pulumi", "stack", "init", "dev"]
        )
        assert result.return_code == 0

    @unittest.mock.patch.object(PulumiService, "_run_pulumi_command")
    def test_config_set(self, mock_run_command):
        """Test configuration setting."""
        mock_run_command.return_value = PulumiResult(0, "Config set", "")
        
        result = self.service.config_set("key", "value")
        
        mock_run_command.assert_called_once_with(
            ["pulumi", "config", "set", "key", "value"]
        )
        assert result.return_code == 0

    @unittest.mock.patch.object(PulumiService, "_run_pulumi_command")
    def test_config_set_secret(self, mock_run_command):
        """Test secret configuration setting."""
        mock_run_command.return_value = PulumiResult(0, "Secret set", "")
        
        result = self.service.config_set("password", "secret123", secret=True)
        
        mock_run_command.assert_called_once_with(
            ["pulumi", "config", "set", "password", "secret123", "--secret"]
        )
        assert result.return_code == 0

    @unittest.mock.patch.object(PulumiService, "_run_pulumi_command")
    def test_up(self, mock_run_command):
        """Test infrastructure deployment."""
        mock_run_command.return_value = PulumiResult(0, "Deployment complete", "")
        
        result = self.service.up()
        
        mock_run_command.assert_called_once_with(
            ["pulumi", "up", "--diff", "--yes"]
        )
        assert result.return_code == 0

    @unittest.mock.patch.object(PulumiService, "_run_pulumi_command")
    def test_destroy(self, mock_run_command):
        """Test infrastructure destruction."""
        mock_run_command.return_value = PulumiResult(0, "Destruction complete", "")
        
        result = self.service.destroy()
        
        mock_run_command.assert_called_once_with(
            ["pulumi", "destroy", "--yes"]
        )
        assert result.return_code == 0

    @unittest.mock.patch.object(PulumiService, "_run_pulumi_command")
    def test_get_stack_outputs(self, mock_run_command):
        """Test getting stack outputs."""
        output_json = '{"resource_group": "test-rg", "cluster_name": "test-cluster"}'
        mock_run_command.return_value = PulumiResult(0, output_json, "")
        
        result = self.service.get_stack_outputs()
        
        expected = {"resource_group": "test-rg", "cluster_name": "test-cluster"}
        assert result == expected

    @unittest.mock.patch.object(PulumiService, "_run_pulumi_command")
    def test_get_stack_outputs_invalid_json(self, mock_run_command):
        """Test getting stack outputs with invalid JSON."""
        mock_run_command.return_value = PulumiResult(0, "invalid json", "")
        
        result = self.service.get_stack_outputs()
        
        assert result == {}

    @unittest.mock.patch.object(PulumiService, "_run_pulumi_command")
    def test_get_stack_outputs_failure(self, mock_run_command):
        """Test getting stack outputs when command fails."""
        mock_run_command.return_value = PulumiResult(1, "", "Command failed")
        
        result = self.service.get_stack_outputs()
        
        assert result == {}