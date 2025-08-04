"""The Pulumi service interface."""
import dataclasses
import os
import sys
from pathlib import Path
from typing import Optional, Dict, Any
import json

try:
    import pulumi
    from pulumi import automation as auto
    PULUMI_AVAILABLE = True
except ImportError:
    PULUMI_AVAILABLE = False


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
        self._stack = None

    def check_poetry_installation(self) -> bool:
        """Checks if Poetry is installed on the host system.

        Returns:
            bool: True if Poetry is installed, False otherwise.
        """
        import subprocess
        try:
            result = subprocess.run(
                ["poetry", "--version"],
                capture_output=True,
                text=True
            )
            return result.returncode == 0
        except FileNotFoundError:
            return False

    def check_installation(self) -> bool:
        """Checks if Pulumi Python SDK is available.

        Returns:
            bool: True if Pulumi Python SDK is installed, False otherwise.
        """
        return PULUMI_AVAILABLE

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

    def _get_or_create_stack(self) -> "auto.Stack":
        """Get or create a Pulumi stack using the Automation API.
        
        Returns:
            auto.Stack: The Pulumi stack instance
        """
        if not PULUMI_AVAILABLE:
            raise ImportError("Pulumi Python SDK is not installed. Install with: pip install pulumi")
        
        if self._stack is not None:
            return self._stack
            
        # Define the Pulumi program inline
        def pulumi_program():
            import os
            component = os.environ.get("MATCHA_COMPONENT", self.config.component)
            
            if component == "remote_state_storage":
                from components.remote_state_storage import create_remote_state_storage
                result = create_remote_state_storage(
                    prefix=pulumi.Config().get("prefix") or "matcha",
                    location=pulumi.Config().get("location") or "East US"
                )
                pulumi.export("storage_account_name", result.storage_account.name)
                pulumi.export("storage_container_name", result.container.name)
                pulumi.export("resource_group_name", result.resource_group.name)
                
            elif component == "default":
                from components.default_stack import create_default_stack
                config = pulumi.Config()
                result = create_default_stack(
                    prefix=config.get("prefix") or "matcha",
                    location=config.get("location") or "East US",
                    config=config
                )
                pulumi.export("resource_group_name", result.resource_group.name)
                pulumi.export("aks_cluster_name", result.aks_cluster.name)
                pulumi.export("storage_account_name", result.storage.storage_account.name)
                pulumi.export("container_registry_name", result.acr.name)
                
            elif component == "llm":
                from components.llm_stack import create_llm_stack
                config = pulumi.Config()
                result = create_llm_stack(
                    prefix=config.get("prefix") or "matcha",
                    location=config.get("location") or "East US",
                    config=config
                )
                pulumi.export("resource_group_name", result.resource_group.name)
                pulumi.export("aks_cluster_name", result.aks_cluster.name)
                pulumi.export("storage_account_name", result.storage.storage_account.name)
                pulumi.export("container_registry_name", result.acr.name)
                pulumi.export("chroma_service_name", result.chroma.service_name)
            else:
                raise ValueError(f"Unknown component: {component}")

        # Create stack using Automation API
        try:
            self._stack = auto.create_or_select_stack(
                stack_name=self.config.stack_name,
                project_name="matcha-ml",
                program=pulumi_program,
                work_dir=self.config.working_dir
            )
        except Exception as e:
            # Try to select existing stack
            try:
                self._stack = auto.select_stack(
                    stack_name=self.config.stack_name,
                    project_name="matcha-ml", 
                    program=pulumi_program,
                    work_dir=self.config.working_dir
                )
            except Exception:
                raise Exception(f"Failed to create or select stack: {e}")
        
        return self._stack





    def config_set(self, key: str, value: str, secret: bool = False) -> PulumiResult:
        """Set a configuration value using Pulumi Automation API.

        Args:
            key: Configuration key
            value: Configuration value
            secret: Whether the value should be encrypted

        Returns:
            PulumiResult: Result of configuration setting
        """
        try:
            stack = self._get_or_create_stack()
            
            if secret:
                stack.set_config(key, auto.ConfigValue(value=value, secret=True))
            else:
                stack.set_config(key, auto.ConfigValue(value=value))
            
            return PulumiResult(
                return_code=0,
                std_out=f"Configuration '{key}' set successfully.",
                std_err=""
            )
            
        except Exception as e:
            return PulumiResult(
                return_code=1,
                std_out="",
                std_err=str(e)
            )

    def preview(self) -> PulumiResult:
        """Show changes that would be made using Automation API.

        Returns:
            PulumiResult: Result of preview command
        """
        try:
            stack = self._get_or_create_stack()
            
            # Run preview
            result = stack.preview()
            
            return PulumiResult(
                return_code=0,
                std_out=f"Preview completed. {len(result.change_summary)} changes planned.",
                std_err=""
            )
            
        except Exception as e:
            return PulumiResult(
                return_code=1,
                std_out="",
                std_err=str(e)
            )

    def up(self, auto_approve: bool = True) -> PulumiResult:
        """Deploy the infrastructure using Pulumi Automation API.

        Args:
            auto_approve: Whether to automatically approve the deployment

        Returns:
            PulumiResult: Result of deployment
        """
        try:
            stack = self._get_or_create_stack()
            
            # Install plugins if needed
            stack.workspace.install_plugin("azure-native", "v2.0.0")
            stack.workspace.install_plugin("kubernetes", "v4.0.0") 
            stack.workspace.install_plugin("helm", "v3.0.0")
            
            # Refresh the stack
            stack.refresh()
            
            # Run the update
            result = stack.up()
            
            return PulumiResult(
                return_code=0 if result.summary.result == "succeeded" else 1,
                std_out=f"Update succeeded. Resources: {len(result.summary.resource_changes or [])} changed.",
                std_err=""
            )
            
        except Exception as e:
            return PulumiResult(
                return_code=1,
                std_out="",
                std_err=str(e)
            )

    def destroy(self, auto_approve: bool = True) -> PulumiResult:
        """Destroy the infrastructure using Pulumi Automation API.

        Args:
            auto_approve: Whether to automatically approve the destruction

        Returns:
            PulumiResult: Result of destruction
        """
        try:
            stack = self._get_or_create_stack()
            
            # Run destroy
            result = stack.destroy()
            
            return PulumiResult(
                return_code=0 if result.summary.result == "succeeded" else 1,
                std_out=f"Destroy succeeded. Resources: {len(result.summary.resource_changes or [])} destroyed.",
                std_err=""
            )
            
        except Exception as e:
            return PulumiResult(
                return_code=1,
                std_out="",
                std_err=str(e)
            )

    def stack_output(self, output_name: Optional[str] = None) -> PulumiResult:
        """Get stack outputs using Automation API.

        Args:
            output_name: Specific output to retrieve (optional)

        Returns:
            PulumiResult: Result containing the outputs
        """
        try:
            stack = self._get_or_create_stack()
            outputs = stack.outputs()
            
            if output_name:
                if output_name in outputs:
                    value = outputs[output_name].value
                    return PulumiResult(
                        return_code=0,
                        std_out=str(value),
                        std_err=""
                    )
                else:
                    return PulumiResult(
                        return_code=1,
                        std_out="",
                        std_err=f"Output '{output_name}' not found"
                    )
            else:
                # Return all outputs as JSON
                result = {k: v.value for k, v in outputs.items()}
                return PulumiResult(
                    return_code=0,
                    std_out=json.dumps(result),
                    std_err=""
                )
                
        except Exception as e:
            return PulumiResult(
                return_code=1,
                std_out="",
                std_err=str(e)
            )

    def get_stack_outputs(self) -> Dict[str, Any]:
        """Get all stack outputs as a dictionary using Automation API.

        Returns:
            Dict[str, Any]: Dictionary of output key-value pairs
        """
        try:
            stack = self._get_or_create_stack()
            outputs = stack.outputs()
            
            # Convert OutputValue objects to regular values
            result = {}
            for key, output_value in outputs.items():
                result[key] = output_value.value
            
            return result
            
        except Exception:
            return {}

    # Compatibility methods to match TerraformService interface
    def init(self) -> PulumiResult:
        """Initialize the Pulumi project using Automation API.

        Returns:
            PulumiResult: Result of initialization
        """
        try:
            # Initialize the stack (creates workspace if needed)
            stack = self._get_or_create_stack()
            
            return PulumiResult(
                return_code=0,
                std_out="Pulumi stack initialized successfully.",
                std_err=""
            )
            
        except Exception as e:
            return PulumiResult(
                return_code=1,
                std_out="",
                std_err=str(e)
            )

    def apply(self) -> PulumiResult:
        """Deploy the infrastructure (compatibility method).

        Returns:
            PulumiResult: Result of deployment
        """
        return self.up(auto_approve=True)
