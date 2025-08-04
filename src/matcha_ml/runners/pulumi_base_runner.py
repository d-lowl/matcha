"""Run Pulumi programs to provision and deprovision resources."""
import os
from abc import abstractmethod
from multiprocessing.pool import ThreadPool
from typing import Any, Optional

import typer

from matcha_ml.cli.ui.emojis import Emojis
from matcha_ml.cli.ui.print_messages import print_error, print_status
from matcha_ml.cli.ui.spinner import Spinner
from matcha_ml.cli.ui.status_message_builders import (
    build_status,
    build_substep_success_status,
    terraform_status_update,  # Reusing for now, could rename to infrastructure_status_update
)
from matcha_ml.errors import MatchaError
from matcha_ml.services.pulumi_service import (
    PulumiConfig,
    PulumiService,
)

SPINNER = "dots"


class PulumiBaseRunner:
    """A PulumiBaseRunner class provides methods that interface with the Pulumi service to facilitate the provisioning and deprovisioning of resources."""

    def __init__(self, working_dir: Optional[str] = None, component: str = "default") -> None:
        """Initialize PulumiBaseRunner class.

        Args:
            working_dir (Optional[str]): Working directory for Pulumi. Defaults to None.
            component (str): Pulumi component to deploy (remote_state_storage, default, llm). Defaults to "default".
        """
        if working_dir is not None:
            working_dir = working_dir
        else:
            working_dir = PulumiConfig().working_dir

        self.pulumi_config = PulumiConfig(working_dir=working_dir, component=component)
        self.pfs = PulumiService(self.pulumi_config)
        self.pulumi_state_dir = self.pfs.get_pulumi_state_dir()

    def _check_pulumi_installation(self) -> None:
        """Checks if Pulumi is installed on the host system.

        Raises:
            typer.Exit: if Pulumi is not installed.
        """
        if not self.pfs.check_installation():
            print_error(f"{Emojis.CROSS.value} Pulumi is not installed")
            print_error(
                "Pulumi is required to run and was not found installed on your machine. "
                "Please visit https://www.pulumi.com/docs/get-started/install/ to install it."
            )
            raise typer.Exit()

    def _check_poetry_installation(self) -> None:
        """Checks if Poetry is installed on the host system.

        Raises:
            typer.Exit: if Poetry is not installed.
        """
        if not self.pfs.check_poetry_installation():
            print_error(f"{Emojis.CROSS.value} Poetry is not installed")
            print_error(
                "Poetry is required for dependency management and was not found installed on your machine. "
                "Please visit https://python-poetry.org/docs/#installation to install it."
            )
            raise typer.Exit()

    def _validate_pulumi_config(self) -> None:
        """Validate the configuration used for creating resources.

        Raises:
            typer.Exit: if `Pulumi.yaml` file not found in working directory.
        """
        if not self.pfs.validate_config():
            print_error(
                "The file Pulumi.yaml was not found in the "
                f"working directory at {self.pfs.config.working_dir}. Please "
                "verify if it exists or run the setup first."
            )
            raise typer.Exit()

    def _validate_kubeconfig(self, base_path: str = ".kube/config") -> None:
        """Check if kubeconfig file exists at location '~/.kube/config', if not create empty config file.

        Args:
            base_path (str): Relative path to location of kubeconfig
        """
        self.pfs.verify_kubectl_config_file(base_path)

    def _setup_pulumi_project(self) -> None:
        """Set up the Pulumi project in the .matcha directory."""
        from pathlib import Path

        # Create the .matcha/infrastructure/pulumi directory
        pulumi_dir = Path(self.pulumi_config.working_dir)
        pulumi_dir.mkdir(parents=True, exist_ok=True)

        # Copy Pulumi files from root to .matcha directory
        project_root = Path(os.getcwd())
        files_to_copy = [
            "Pulumi.yaml",
            "pyproject-pulumi.toml",
            "__main__.py",
            "Pulumi.dev.yaml"
        ]

        for file_name in files_to_copy:
            src = project_root / file_name
            dst_name = "pyproject.toml" if file_name == "pyproject-pulumi.toml" else file_name
            dst = pulumi_dir / dst_name
            if src.exists():
                dst.write_text(src.read_text())

        # Copy components directory
        components_src = project_root / "components"
        components_dst = pulumi_dir / "components"

        if components_src.exists():
            components_dst.mkdir(exist_ok=True)
            for py_file in components_src.glob("*.py"):
                (components_dst / py_file.name).write_text(py_file.read_text())

    def _initialize_pulumi(self, msg: str = "", destroy: bool = False) -> None:
        """Initialize Pulumi stack and install dependencies.

        Args:
            msg (str): Message to display. Default is empty string.
            destroy (bool): whether this function is being called in a destructive context

        Raises:
            MatchaError: if Pulumi initialization failed.
        """
        if self.pulumi_state_dir.exists() and not destroy:
            print_status(
                build_status(
                    f"matcha {Emojis.MATCHA.value} has already been initialized. Skipping this step..."
                )
            )
        else:
            print_status(
                build_status(
                    f"\n{Emojis.WAITING.value} Brewing matcha {Emojis.MATCHA.value}...\n"
                )
            )

            with Spinner("Initializing"):
                # Set up Pulumi project files
                self._setup_pulumi_project()

                # Initialize Pulumi (this will select or create stack and install dependencies)
                pulumi_result = self.pfs.init()

                if pulumi_result.return_code != 0:
                    print_error("Pulumi initialization failed.")
                    raise MatchaError(f"Pulumi error: {pulumi_result.std_err}")

            print_status(
                build_substep_success_status(
                    f"{Emojis.CHECKMARK.value} {msg} {Emojis.MATCHA.value} initialized!\n"
                )
            )

    def _check_matcha_directory_exists(self) -> None:
        """Checks if .matcha directory exists within the current working directory.

        Raises:
            typer.Exit: if the .matcha directory does not exist.
            typer.Exit: if the .matcha directory does not contain the required files to deploy resources.
        """
        if not self.pfs.check_matcha_directory_exists():
            print_error(
                f"Error, the .matcha directory does not exist in {os.getcwd()} . Please ensure you are trying to destroy resources that you have provisioned in the current working directory."
            )
            raise typer.Exit()

        if not self.pfs.check_matcha_directory_integrity():
            print_error(
                "Error, the .matcha directory does not contain files relating to deployed resources. Please ensure you are trying to destroy resources that you have provisioned in the current working directory."
            )
            raise typer.Exit()

    def _apply_pulumi(self, msg: str = "") -> None:
        """Run pulumi up to create resources on cloud.

        Args:
            msg (str): Name of the type of resource (e.g. "Remote State" or "Matcha").

        Raises:
            MatchaError: if 'pulumi up' failed.
        """
        with Spinner("Applying") as spinner:
            pool = ThreadPool(processes=1)
            _ = pool.apply_async(terraform_status_update, (spinner,))  # Reusing status update function

            pulumi_result = self.pfs.up(auto_approve=True)

            pool.terminate()

            if pulumi_result.return_code != 0:
                raise MatchaError(f"Pulumi error: {pulumi_result.std_err}")

        if msg:
            print_status(
                build_substep_success_status(
                    f"{Emojis.CHECKMARK.value} {msg} resources have been provisioned!\n"
                )
            )
        else:
            print_status(
                build_substep_success_status(
                    f"{Emojis.CHECKMARK.value} Resources have been provisioned!\n"
                )
            )

    def _destroy_pulumi(self, msg: str = "") -> None:
        """Destroy the provisioned resources.

        Args:
            msg (str): Message to display. Default is empty string.

        Raises:
            MatchaError: if 'pulumi destroy' failed.
        """
        print()
        print_status(
            build_status(f"{Emojis.WAITING.value} Destroying {msg} resources...")
        )
        print()
        with Spinner("Destroying"):
            pulumi_result = self.pfs.destroy(auto_approve=True)

            if pulumi_result.return_code != 0:
                raise MatchaError(f"Pulumi error: {pulumi_result.std_err}")

    @abstractmethod
    def provision(self) -> Any:
        """Provision resources required for the deployment."""
        pass

    @abstractmethod
    def deprovision(self) -> Any:
        """Destroy the provisioned resources."""
        pass
