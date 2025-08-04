"""The Pulumi service interface."""
import dataclasses
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional, Dict, Any
import json


@dataclasses.dataclass
class PulumiResult:
    """A class to hold the result of the pulumi commands."""

    return_code: int
    std_out: str
    std_err: str


@dataclasses.dataclass
class PulumiConfig:
    """Configuration required for Pulumi."""

    # Path to Pulumi project
    working_dir: str = os.path.join(
        os.getcwd(), ".matcha", "infrastructure", "pulumi"
    )

    # if set to False pulumi output will be printed to stdout/stderr
    # else no output will be printed and (ret_code, out, err) tuple will be returned
    capture_output: bool = True

    # Pulumi stack name
    stack_name: str = "dev"

    # Component to deploy (remote_state_storage, default, llm)
    component: str = "default"


class PulumiService:
    """PulumiService class to provision and deprovision resources."""

    def __init__(self, pulumi_config: PulumiConfig):
        """Constructor for the PulumiService class."""
        self.config = pulumi_config

    def check_installation(self) -> bool:
        """Checks if Pulumi is installed on the host system.

        Returns:
            bool: True if Pulumi is installed, False otherwise.
        """
        try:
            result = subprocess.run(
                ["pulumi", "version"],
                capture_output=True,
                text=True
            )
            return result.returncode == 0
        except FileNotFoundError:
            return False

    def verify_kubectl_config_file(self, config_path: str = ".kube/config") -> None:
        """Checks if kubeconfig is present at location ~/.kube/config.

        Args:
            config_path (str): Relative path to location of kubeconfig

        If not, it creates an empty config file.
        """
        kubeconfig_path = os.path.join(os.path.expanduser("~"), config_path)

        if not os.path.exists(kubeconfig_path):
            os.makedirs(os.path.dirname(kubeconfig_path), exist_ok=True)
            with open(kubeconfig_path, "a"):
                pass

    def check_matcha_directory_integrity(self) -> bool:
        """Checks the integrity of the .matcha directory.

        Returns:
            bool: False if .matcha directory is empty else True.
        """
        matcha_dir_path = os.path.join(os.getcwd(), ".matcha")
        
        if not os.path.exists(matcha_dir_path):
            return False
            
        return len(os.listdir(matcha_dir_path)) != 0

    def check_matcha_directory_exists(self) -> bool:
        """Checks if .matcha directory exists within the current working directory.

        Returns:
            bool: True when the .matcha directory exists.
        """
        matcha_dir_path = os.path.join(os.getcwd(), ".matcha")
        return os.path.isdir(matcha_dir_path)

    def validate_config(self) -> bool:
        """Validate the configuration used for creating resources.

        Returns:
            bool: True when the Pulumi project exists.
        """
        pulumi_yaml = os.path.join(self.config.working_dir, "Pulumi.yaml")
        return Path(pulumi_yaml).exists()

    def get_pulumi_state_dir(self) -> Path:
        """Get the path to the Pulumi state directory.

        Returns:
            Path: a Path object that represents the path to the Pulumi state directory.
        """
        return Path(os.path.join(self.config.working_dir, ".pulumi"))

    def _run_pulumi_command(self, command: list, env_vars: Optional[Dict[str, str]] = None) -> PulumiResult:
        """Run a Pulumi command with proper environment setup.
        
        Args:
            command: List of command arguments
            env_vars: Additional environment variables
            
        Returns:
            PulumiResult: Result of the command execution
        """
        # Set up environment
        env = os.environ.copy()
        env["MATCHA_COMPONENT"] = self.config.component
        
        if env_vars:
            env.update(env_vars)

        try:
            result = subprocess.run(
                command,
                cwd=self.config.working_dir,
                capture_output=self.config.capture_output,
                text=True,
                env=env
            )
            
            return PulumiResult(
                return_code=result.returncode,
                std_out=result.stdout or "",
                std_err=result.stderr or ""
            )
        except FileNotFoundError as e:
            return PulumiResult(
                return_code=1,
                std_out="",
                std_err=f"Pulumi command not found: {e}"
            )

    def stack_init(self) -> PulumiResult:
        """Initialize a new Pulumi stack.

        Returns:
            PulumiResult: Result of stack initialization
        """
        command = ["pulumi", "stack", "init", self.config.stack_name]
        return self._run_pulumi_command(command)

    def stack_select(self) -> PulumiResult:
        """Select an existing Pulumi stack.

        Returns:
            PulumiResult: Result of stack selection
        """
        command = ["pulumi", "stack", "select", self.config.stack_name]
        return self._run_pulumi_command(command)

    def install_dependencies(self) -> PulumiResult:
        """Install Python dependencies for the Pulumi project.

        Returns:
            PulumiResult: Result of dependency installation
        """
        command = [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"]
        return self._run_pulumi_command(command)

    def config_set(self, key: str, value: str, secret: bool = False) -> PulumiResult:
        """Set a configuration value.

        Args:
            key: Configuration key
            value: Configuration value
            secret: Whether the value should be encrypted

        Returns:
            PulumiResult: Result of configuration setting
        """
        command = ["pulumi", "config", "set", key, value]
        if secret:
            command.append("--secret")
        
        return self._run_pulumi_command(command)

    def preview(self) -> PulumiResult:
        """Run `pulumi preview` to show changes that would be made.

        Returns:
            PulumiResult: Result of preview command
        """
        command = ["pulumi", "preview", "--diff"]
        return self._run_pulumi_command(command)

    def up(self, auto_approve: bool = True) -> PulumiResult:
        """Run `pulumi up` to deploy the infrastructure.

        Args:
            auto_approve: Whether to automatically approve the deployment

        Returns:
            PulumiResult: Result of deployment
        """
        command = ["pulumi", "up", "--diff"]
        if auto_approve:
            command.append("--yes")
        
        return self._run_pulumi_command(command)

    def destroy(self, auto_approve: bool = True) -> PulumiResult:
        """Run `pulumi destroy` to destroy the infrastructure.

        Args:
            auto_approve: Whether to automatically approve the destruction

        Returns:
            PulumiResult: Result of destruction
        """
        command = ["pulumi", "destroy"]
        if auto_approve:
            command.append("--yes")
        
        return self._run_pulumi_command(command)

    def stack_output(self, output_name: Optional[str] = None) -> PulumiResult:
        """Get stack outputs.

        Args:
            output_name: Specific output to retrieve (optional)

        Returns:
            PulumiResult: Result containing the outputs
        """
        command = ["pulumi", "stack", "output"]
        if output_name:
            command.append(output_name)
        else:
            command.append("--json")
        
        return self._run_pulumi_command(command)

    def get_stack_outputs(self) -> Dict[str, Any]:
        """Get all stack outputs as a dictionary.

        Returns:
            Dict[str, Any]: Dictionary of output key-value pairs
        """
        result = self.stack_output()
        if result.return_code == 0 and result.std_out:
            try:
                return json.loads(result.std_out)
            except json.JSONDecodeError:
                return {}
        return {}

    # Compatibility methods to match TerraformService interface
    def init(self) -> PulumiResult:
        """Initialize the Pulumi project (compatibility method).

        Returns:
            PulumiResult: Result of initialization
        """
        # Try to select existing stack first, if that fails, create new one
        select_result = self.stack_select()
        if select_result.return_code != 0:
            init_result = self.stack_init()
            if init_result.return_code != 0:
                return init_result
        
        # Install dependencies
        return self.install_dependencies()

    def apply(self) -> PulumiResult:
        """Deploy the infrastructure (compatibility method).

        Returns:
            PulumiResult: Result of deployment
        """
        return self.up(auto_approve=True)