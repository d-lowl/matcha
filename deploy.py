#!/usr/bin/env python3
"""
Deployment script for Matcha ML infrastructure using Pulumi.
This script provides a convenient way to deploy different components.
"""

import argparse
import os
import sys
from pathlib import Path

# Add the current directory to Python path for imports
sys.path.insert(0, str(Path(__file__).parent))

from src.matcha_ml.services.pulumi_service import PulumiService, PulumiConfig


def setup_pulumi_project():
    """Set up the Pulumi project structure in .matcha directory."""
    matcha_dir = Path(".matcha")
    pulumi_dir = matcha_dir / "infrastructure" / "pulumi"
    
    # Create directories
    pulumi_dir.mkdir(parents=True, exist_ok=True)
    (pulumi_dir / "components").mkdir(exist_ok=True)
    
    # Copy Pulumi files
    files_to_copy = [
        "Pulumi.yaml",
        "pyproject-pulumi.toml", 
        "__main__.py",
        "Pulumi.dev.yaml"
    ]
    
    for file_name in files_to_copy:
        src = Path(file_name)
        dst_name = "pyproject.toml" if file_name == "pyproject-pulumi.toml" else file_name
        dst = pulumi_dir / dst_name
        if src.exists():
            dst.write_text(src.read_text())
    
    # Copy components
    components_src = Path("components")
    components_dst = pulumi_dir / "components"
    
    if components_src.exists():
        for py_file in components_src.glob("*.py"):
            (components_dst / py_file.name).write_text(py_file.read_text())


def deploy_component(component: str, stack: str = "dev", auto_approve: bool = False):
    """Deploy a specific component using Pulumi.
    
    Args:
        component: Component to deploy (remote_state_storage, default, llm)
        stack: Stack name to use
        auto_approve: Whether to automatically approve the deployment
    """
    # Set up Pulumi project
    setup_pulumi_project()
    
    # Configure Pulumi service
    config = PulumiConfig(
        stack_name=stack,
        component=component,
        working_dir=str(Path(".matcha") / "infrastructure" / "pulumi")
    )
    
    service = PulumiService(config)
    
    # Check Pulumi installation
    if not service.check_installation():
        print("❌ Pulumi is not installed. Please install Pulumi first.")
        print("   Visit: https://www.pulumi.com/docs/get-started/install/")
        return False
    
    # Check Poetry installation
    if not service.check_poetry_installation():
        print("❌ Poetry is not installed. Please install Poetry first.")
        print("   Visit: https://python-poetry.org/docs/#installation")
        return False
    
    print(f"🚀 Deploying {component} component to {stack} stack...")
    
    # Initialize stack
    print("📦 Initializing Pulumi stack...")
    init_result = service.init()
    if init_result.return_code != 0:
        print(f"❌ Failed to initialize: {init_result.std_err}")
        return False
    
    # Set component configuration
    config_result = service.config_set("component", component)
    if config_result.return_code != 0:
        print(f"❌ Failed to set component config: {config_result.std_err}")
        return False
    
    # Preview changes
    if not auto_approve:
        print("👀 Previewing changes...")
        preview_result = service.preview()
        if preview_result.return_code != 0:
            print(f"❌ Preview failed: {preview_result.std_err}")
            return False
        
        confirm = input("\nDo you want to proceed with the deployment? (y/N): ")
        if confirm.lower() not in ['y', 'yes']:
            print("❌ Deployment cancelled.")
            return False
    
    # Deploy
    print("🔨 Deploying infrastructure...")
    deploy_result = service.up(auto_approve=True)
    
    if deploy_result.return_code == 0:
        print("✅ Deployment successful!")
        
        # Show outputs
        outputs = service.get_stack_outputs()
        if outputs:
            print("\n📋 Stack Outputs:")
            for key, value in outputs.items():
                print(f"  {key}: {value}")
        
        return True
    else:
        print(f"❌ Deployment failed: {deploy_result.std_err}")
        return False


def destroy_component(component: str, stack: str = "dev", auto_approve: bool = False):
    """Destroy a specific component using Pulumi.
    
    Args:
        component: Component to destroy
        stack: Stack name to use
        auto_approve: Whether to automatically approve the destruction
    """
    config = PulumiConfig(
        stack_name=stack,
        component=component,
        working_dir=str(Path(".matcha") / "infrastructure" / "pulumi")
    )
    
    service = PulumiService(config)
    
    if not auto_approve:
        confirm = input(f"⚠️  Are you sure you want to destroy {component}? This cannot be undone! (y/N): ")
        if confirm.lower() not in ['y', 'yes']:
            print("❌ Destruction cancelled.")
            return False
    
    print(f"💥 Destroying {component} component...")
    result = service.destroy(auto_approve=True)
    
    if result.return_code == 0:
        print("✅ Destruction successful!")
        return True
    else:
        print(f"❌ Destruction failed: {result.std_err}")
        return False


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Deploy Matcha ML infrastructure with Pulumi")
    parser.add_argument("action", choices=["deploy", "destroy"], help="Action to perform")
    parser.add_argument("component", choices=["remote_state_storage", "default", "llm"], 
                       help="Component to deploy or destroy")
    parser.add_argument("--stack", default="dev", help="Pulumi stack name (default: dev)")
    parser.add_argument("--auto-approve", action="store_true", 
                       help="Automatically approve without prompting")
    
    args = parser.parse_args()
    
    if args.action == "deploy":
        success = deploy_component(args.component, args.stack, args.auto_approve)
    else:
        success = destroy_component(args.component, args.stack, args.auto_approve)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()