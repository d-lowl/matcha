"""Run Pulumi programs to provision and deprovision state bucket resource."""
import os
import shutil
from typing import Tuple

from matcha_ml.cli.ui.print_messages import print_error
from matcha_ml.runners.pulumi_base_runner import PulumiBaseRunner


class RemoteStateRunner(PulumiBaseRunner):
    """A RemoteStateRunner class that provisioning and deprovisioning resources for the remote state."""

    def __init__(
        self,
        working_dir: str = os.path.join(
            os.getcwd(), ".matcha", "infrastructure", "pulumi"
        ),
    ) -> None:
        """Initialize a RemoteStateRunner.

        Args:
            working_dir (str): Working directory for Pulumi.
            Defaults to os.path.join(os.getcwd(), ".matcha", "infrastructure", "pulumi").
        """
        super().__init__(working_dir=working_dir, component="remote_state_storage")

    def _get_pulumi_output(self) -> Tuple[str, str, str]:
        """Return the account name and the container name from Pulumi output.

        Returns:
            Tuple[str, str, str]: account name, the container name and azure resource_group_name.
        """
        pulumi_outputs = self.pfs.get_stack_outputs()

        account_name = ""
        container_name = ""
        resource_group_name = ""

        # Pulumi outputs are directly accessible (no nested 'value' structure like Terraform)
        account_name = pulumi_outputs.get("storage_account_name", "")
        resource_group_name = pulumi_outputs.get("resource_group_name", "")
        container_name = pulumi_outputs.get("storage_container_name", "")

        return account_name, container_name, resource_group_name

    def _clean_up(self) -> None:
        """Remove the whole .matcha directory when destroy full is run."""
        matcha_template_dir = os.path.join(os.getcwd(), ".matcha")
        try:
            shutil.rmtree(matcha_template_dir)
        except FileNotFoundError:
            print_error(
                f"Failed to remove the .matcha directory at {matcha_template_dir}, directory not found."
            )

    def provision(self) -> Tuple[str, str, str]:
        """Provision resources required for the deployment.

        Returns:
            Tuple[str, str, str]: account name, the container name and azure resource_group_name.
        """
        self._check_pulumi_installation()
        self._check_poetry_installation()
        self._validate_kubeconfig(base_path=".kube/config")
        self._initialize_pulumi(msg="Remote State")
        self._apply_pulumi(msg="Remote State")
        return self._get_pulumi_output()

    def deprovision(self) -> None:
        """Destroy the provisioned resources."""
        self._check_matcha_directory_exists()
        self._check_pulumi_installation()
        self._check_poetry_installation()
        self._initialize_pulumi(msg="Remote State")
        self._destroy_pulumi(msg="Remote State")
        self._clean_up()
