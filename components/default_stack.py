"""
Default MLOps stack component for Pulumi.
This creates the main infrastructure including AKS, storage, container registry,
MLflow, ZenML, and Seldon.
"""

import pulumi
import pulumi_azure_native as azure
import pulumi_kubernetes as k8s
import pulumi_helm as helm
from typing import NamedTuple
import base64


class DefaultStack(NamedTuple):
    """Return type for default stack creation."""
    resource_group: azure.resources.ResourceGroup
    aks_cluster: azure.containerservice.ManagedCluster
    storage: 'StorageResources'
    zenml_storage: 'ZenMLStorage'
    dvc_storage: 'DVCStorage'
    acr: azure.containerregistry.Registry
    mlflow: helm.Release
    zenserver: helm.Release
    seldon: helm.Release


class StorageResources(NamedTuple):
    """Storage resources for general use."""
    storage_account: azure.storage.StorageAccount
    container: azure.storage.BlobContainer


class ZenMLStorage(NamedTuple):
    """ZenML specific storage resources."""
    storage_account: azure.storage.StorageAccount
    container: azure.storage.BlobContainer
    role_assignment: azure.authorization.RoleAssignment


class DVCStorage(NamedTuple):
    """Data Version Control storage resources."""
    storage_account: azure.storage.StorageAccount
    container: azure.storage.BlobContainer


def create_default_stack(prefix: str, location: str, config: pulumi.Config) -> DefaultStack:
    """
    Create the default MLOps infrastructure stack.
    
    Args:
        prefix: Prefix for resource names
        location: Azure region
        config: Pulumi configuration object
        
    Returns:
        DefaultStack: Named tuple with all created resources
    """
    
    # Create resource group
    resource_group = azure.resources.ResourceGroup(
        f"{prefix}-rg",
        resource_group_name=f"{prefix}-resources",
        location=location,
        tags={
            "Environment": "production",
            "Component": "default-stack",
            "ManagedBy": "pulumi"
        }
    )
    
    # Create AKS cluster
    aks_cluster = azure.containerservice.ManagedCluster(
        f"{prefix}-aks",
        resource_name=f"{prefix}-k8s",
        resource_group_name=resource_group.name,
        location=location,
        dns_prefix=f"{prefix}-k8s",
        agent_pool_profiles=[
            azure.containerservice.ManagedClusterAgentPoolProfileArgs(
                name="default",
                vm_size="Standard_DS3_v2",
                count=1,
                min_count=1,
                max_count=3,
                enable_auto_scaling=True,
                type=azure.containerservice.AgentPoolType.VIRTUAL_MACHINE_SCALE_SETS,
                mode=azure.containerservice.AgentPoolMode.SYSTEM
            )
        ],
        identity=azure.containerservice.ManagedClusterIdentityArgs(
            type=azure.containerservice.ResourceIdentityType.SYSTEM_ASSIGNED
        ),
        tags={
            "Environment": "production",
            "Component": "kubernetes",
            "ManagedBy": "pulumi"
        }
    )
    
    # Create general storage account and container
    storage_account = azure.storage.StorageAccount(
        f"{prefix}-storage",
        account_name=f"st{prefix}acc",
        resource_group_name=resource_group.name,
        location=location,
        kind=azure.storage.Kind.STORAGE_V2,
        sku=azure.storage.SkuArgs(
            name=azure.storage.SkuName.STANDARD_LRS,
        ),
        access_tier=azure.storage.AccessTier.HOT,
        allow_blob_public_access=True,
        tags={
            "Environment": "production",
            "Component": "storage",
            "ManagedBy": "pulumi"
        }
    )
    
    storage_container = azure.storage.BlobContainer(
        f"{prefix}-storage-container",
        container_name=f"{prefix}store",
        account_name=storage_account.name,
        resource_group_name=resource_group.name,
        public_access=azure.storage.PublicAccess.CONTAINER
    )
    
    # Create ZenML storage account and container
    zenml_storage_account = azure.storage.StorageAccount(
        f"{prefix}-zenml-storage",
        account_name=f"{prefix}zenmlacc",
        resource_group_name=resource_group.name,
        location=location,
        kind=azure.storage.Kind.STORAGE_V2,
        sku=azure.storage.SkuArgs(
            name=azure.storage.SkuName.STANDARD_LRS,
        ),
        tags={
            "Environment": "production",
            "Component": "zenml-storage",
            "ManagedBy": "pulumi"
        }
    )
    
    zenml_container = azure.storage.BlobContainer(
        f"{prefix}-zenml-container",
        container_name=f"{prefix}artifactstore",
        account_name=zenml_storage_account.name,
        resource_group_name=resource_group.name,
        public_access=azure.storage.PublicAccess.NONE
    )
    
    # Create role assignment for AKS to access ZenML storage
    zenml_role_assignment = azure.authorization.RoleAssignment(
        f"{prefix}-zenml-role",
        principal_id=aks_cluster.identity_profile["kubeletidentity"].object_id,
        role_definition_id=pulumi.Output.concat(
            "/subscriptions/", azure.core.get_client_config().subscription_id,
            "/providers/Microsoft.Authorization/roleDefinitions/b24988ac-6180-42a0-ab88-20f7382dd24c"  # Contributor role
        ),
        scope=zenml_storage_account.id
    )
    
    # Create Data Version Control storage
    dvc_storage_account = azure.storage.StorageAccount(
        f"{prefix}-dvc-storage",
        account_name=f"{prefix}dvcacc",
        resource_group_name=resource_group.name,
        location=location,
        kind=azure.storage.Kind.STORAGE_V2,
        sku=azure.storage.SkuArgs(
            name=azure.storage.SkuName.STANDARD_LRS,
        ),
        access_tier=azure.storage.AccessTier.HOT,
        allow_blob_public_access=True,
        tags={
            "Environment": "production",
            "Component": "dvc-storage",
            "ManagedBy": "pulumi"
        }
    )
    
    dvc_container = azure.storage.BlobContainer(
        f"{prefix}-dvc-container",
        container_name=f"{prefix}dvcstore",
        account_name=dvc_storage_account.name,
        resource_group_name=resource_group.name,
        public_access=azure.storage.PublicAccess.CONTAINER
    )
    
    # Create Azure Container Registry
    acr = azure.containerregistry.Registry(
        f"{prefix}-acr",
        registry_name=f"cr{prefix}",
        resource_group_name=resource_group.name,
        location=location,
        sku=azure.containerregistry.SkuArgs(
            name="Standard"
        ),
        admin_user_enabled=True,
        tags={
            "Environment": "production",
            "Component": "container-registry",
            "ManagedBy": "pulumi"
        }
    )
    
    # Create role assignment for AKS to pull from ACR
    acr_role_assignment = azure.authorization.RoleAssignment(
        f"{prefix}-acr-role",
        principal_id=aks_cluster.identity_profile["kubeletidentity"].object_id,
        role_definition_id=pulumi.Output.concat(
            "/subscriptions/", azure.core.get_client_config().subscription_id,
            "/providers/Microsoft.Authorization/roleDefinitions/7f951dda-4ed3-4680-a7ca-43fe172d538d"  # AcrPull role
        ),
        scope=acr.id
    )
    
    # Create Kubernetes provider for Helm deployments
    k8s_provider = k8s.Provider(
        f"{prefix}-k8s-provider",
        kubeconfig=aks_cluster.kube_configs[0].raw_config,
        opts=pulumi.ResourceOptions(depends_on=[aks_cluster])
    )
    
    # Deploy MLflow using Helm
    mlflow_release = helm.Release(
        "mlflow",
        chart="mlflow",
        repository_opts=helm.RepositoryOptsArgs(
            repo="https://community-charts.github.io/helm-charts"
        ),
        values={
            "defaultArtifactRoot": f"azure://{storage_container.name}",
            "backendStore": {
                "databaseConnectionString": "sqlite:///mlflow/mlflow.db"
            }
        },
        opts=pulumi.ResourceOptions(
            provider=k8s_provider,
            depends_on=[aks_cluster, storage_account]
        )
    )
    
    # Deploy ZenML Server
    username = config.get("username") or "default"
    password = config.require_secret("password")
    zenmlserver_version = config.get("zenmlserver_version") or "latest"
    
    zenserver_release = helm.Release(
        "zenserver",
        chart="zenmlserver",
        repository_opts=helm.RepositoryOptsArgs(
            repo="https://zenml-io.github.io/zenml"
        ),
        values={
            "zenmlserver": {
                "version": zenmlserver_version,
                "username": username,
                "password": password
            }
        },
        opts=pulumi.ResourceOptions(
            provider=k8s_provider,
            depends_on=[aks_cluster]
        )
    )
    
    # Deploy Seldon Core
    seldon_name = config.get("seldon_name") or "seldon"
    seldon_namespace = config.get("seldon_namespace") or "seldon-system"
    
    # Create Seldon namespace
    seldon_ns = k8s.core.v1.Namespace(
        "seldon-namespace",
        metadata=k8s.meta.v1.ObjectMetaArgs(
            name=seldon_namespace
        ),
        opts=pulumi.ResourceOptions(
            provider=k8s_provider,
            depends_on=[aks_cluster]
        )
    )
    
    seldon_release = helm.Release(
        "seldon",
        chart="seldon-core-operator",
        repository_opts=helm.RepositoryOptsArgs(
            repo="https://storage.googleapis.com/seldon-charts"
        ),
        namespace=seldon_namespace,
        values={
            "usageMetrics": {
                "enabled": True
            },
            "istio": {
                "enabled": True
            }
        },
        opts=pulumi.ResourceOptions(
            provider=k8s_provider,
            depends_on=[aks_cluster, seldon_ns]
        )
    )
    
    return DefaultStack(
        resource_group=resource_group,
        aks_cluster=aks_cluster,
        storage=StorageResources(
            storage_account=storage_account,
            container=storage_container
        ),
        zenml_storage=ZenMLStorage(
            storage_account=zenml_storage_account,
            container=zenml_container,
            role_assignment=zenml_role_assignment
        ),
        dvc_storage=DVCStorage(
            storage_account=dvc_storage_account,
            container=dvc_container
        ),
        acr=acr,
        mlflow=mlflow_release,
        zenserver=zenserver_release,
        seldon=seldon_release
    )