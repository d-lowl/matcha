"""
Remote state storage component for Pulumi.
This creates Azure storage resources for storing Pulumi state.
"""

import pulumi
import pulumi_azure_native as azure
from typing import NamedTuple


class RemoteStateStorage(NamedTuple):
    """Return type for remote state storage creation."""
    resource_group: azure.resources.ResourceGroup
    storage_account: azure.storage.StorageAccount
    container: azure.storage.BlobContainer


def create_remote_state_storage(prefix: str, location: str) -> RemoteStateStorage:
    """
    Create Azure storage resources for Pulumi state storage.
    
    Args:
        prefix: Prefix for resource names
        location: Azure region
        
    Returns:
        RemoteStateStorage: Named tuple with created resources
    """
    
    # Create resource group
    resource_group = azure.resources.ResourceGroup(
        f"{prefix}-rg",
        resource_group_name=f"{prefix}-resources",
        location=location,
        tags={
            "Environment": "infrastructure",
            "Component": "remote-state-storage",
            "ManagedBy": "pulumi"
        }
    )
    
    # Create storage account for state storage
    storage_account = azure.storage.StorageAccount(
        f"{prefix}-state-storage",
        account_name=f"{prefix}statestacc",
        resource_group_name=resource_group.name,
        location=location,
        kind=azure.storage.Kind.STORAGE_V2,
        sku=azure.storage.SkuArgs(
            name=azure.storage.SkuName.STANDARD_LRS,
        ),
        access_tier=azure.storage.AccessTier.HOT,
        allow_blob_public_access=True,
        tags={
            "Environment": "infrastructure",
            "Component": "remote-state-storage", 
            "ManagedBy": "pulumi"
        }
    )
    
    # Create blob container for state files
    container = azure.storage.BlobContainer(
        f"{prefix}-state-container",
        container_name=f"{prefix}statestore",
        account_name=storage_account.name,
        resource_group_name=resource_group.name,
        public_access=azure.storage.PublicAccess.CONTAINER
    )
    
    return RemoteStateStorage(
        resource_group=resource_group,
        storage_account=storage_account,
        container=container
    )