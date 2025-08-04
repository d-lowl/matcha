"""Run Pulumi programs to provision and deprovision resources."""
import os
import shutil

from matcha_ml.runners.pulumi_base_runner import PulumiBaseRunner
from matcha_ml.state.matcha_state import MatchaStateService
from matcha_ml.config import MatchaConfigService


class AzureRunner(PulumiBaseRunner):
    """A Runner class provides methods that interface with the Pulumi service to facilitate the provisioning and deprovisioning of resources."""

    def __init__(self) -> None:
        """Initialize AzureRunner class."""
        # Get the stack type to determine which component to deploy
        stack = MatchaConfigService.get_stack()
        component = "default" if stack is None else stack.value.lower()
        super().__init__(component=component)

    def remove_matcha_dir(self) -> None:
        """Removes the project's .matcha directory"."""
        project_directory = os.getcwd()
        target = os.path.join(project_directory, ".matcha")
        if os.path.exists(target):
            shutil.rmtree(target)

    def provision(self) -> MatchaStateService:
        """Provision resources required for the deployment.

        Returns:
            (MatchaStateService): a MatchaStateService instance initialized with Pulumi output
        """
        self._check_pulumi_installation()
        self._check_poetry_installation()
        self._validate_kubeconfig(base_path=".kube/config")
        self._initialize_pulumi(msg="Matcha")
        self._apply_pulumi(msg="Matcha")

        # Get Pulumi outputs and convert to format expected by MatchaStateService
        pulumi_outputs = self.pfs.get_stack_outputs()
        return MatchaStateService(pulumi_output=pulumi_outputs)

    def deprovision(self) -> None:
        """Destroy the provisioned resources."""
        self._check_matcha_directory_exists()
        self._check_pulumi_installation()
        self._check_poetry_installation()
        self._initialize_pulumi(msg="Matcha", destroy=True)
        self._destroy_pulumi(msg="Matcha")
