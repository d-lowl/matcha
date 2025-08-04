"""
Main Pulumi program for Matcha ML infrastructure.
This file serves as the entry point and can be used to deploy individual components.
"""

import pulumi
import os

# Import our component modules
from components import remote_state_storage, default_stack, llm_stack

# Get configuration
config = pulumi.Config()
prefix = config.get("prefix") or "matcha"
location = config.get("location") or "East US"

# Determine which component to deploy based on environment variable or config
component = os.environ.get("MATCHA_COMPONENT", config.get("component", "default"))

if component == "remote_state_storage":
    # Deploy remote state storage
    storage = remote_state_storage.create_remote_state_storage(
        prefix=prefix,
        location=location
    )
    
    # Export storage account details for state backend
    pulumi.export("storage_account_name", storage.storage_account.name)
    pulumi.export("storage_container_name", storage.container.name)
    pulumi.export("resource_group_name", storage.resource_group.name)

elif component == "default":
    # Deploy default MLOps stack
    stack = default_stack.create_default_stack(
        prefix=prefix,
        location=location,
        config=config
    )
    
    # Export important outputs
    pulumi.export("resource_group_name", stack.resource_group.name)
    pulumi.export("aks_cluster_name", stack.aks_cluster.name)
    pulumi.export("storage_account_name", stack.storage.storage_account.name)
    pulumi.export("container_registry_name", stack.acr.name)

elif component == "llm":
    # Deploy LLM-enhanced stack
    stack = llm_stack.create_llm_stack(
        prefix=prefix,
        location=location,
        config=config
    )
    
    # Export important outputs
    pulumi.export("resource_group_name", stack.resource_group.name)
    pulumi.export("aks_cluster_name", stack.aks_cluster.name)
    pulumi.export("storage_account_name", stack.storage.storage_account.name)
    pulumi.export("container_registry_name", stack.acr.name)
    pulumi.export("chroma_service_name", stack.chroma.service_name)

else:
    raise ValueError(f"Unknown component: {component}. Must be one of: remote_state_storage, default, llm")