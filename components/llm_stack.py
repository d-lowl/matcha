"""
LLM-enhanced MLOps stack component for Pulumi.
This creates the complete infrastructure including everything from the default stack
plus the Chroma vector database for LLM applications.
"""

import pulumi
import pulumi_azure_native as azure
import pulumi_kubernetes as k8s
import pulumi_helm as helm
from typing import NamedTuple
from .default_stack import (
    create_default_stack, 
    DefaultStack,
    StorageResources,
    ZenMLStorage,
    DVCStorage
)


class ChromaDatabase(NamedTuple):
    """Chroma vector database deployment."""
    release: helm.Release
    service_name: str


class LLMStack(NamedTuple):
    """Return type for LLM stack creation."""
    resource_group: azure.resources.ResourceGroup
    aks_cluster: azure.containerservice.ManagedCluster
    storage: StorageResources
    zenml_storage: ZenMLStorage
    dvc_storage: DVCStorage
    acr: azure.containerregistry.Registry
    mlflow: helm.Release
    zenserver: helm.Release
    seldon: helm.Release
    chroma: ChromaDatabase


def create_llm_stack(prefix: str, location: str, config: pulumi.Config) -> LLMStack:
    """
    Create the LLM-enhanced MLOps infrastructure stack.
    
    Args:
        prefix: Prefix for resource names
        location: Azure region
        config: Pulumi configuration object
        
    Returns:
        LLMStack: Named tuple with all created resources including Chroma
    """
    
    # Create the base default stack first
    default_stack = create_default_stack(prefix, location, config)
    
    # Create Kubernetes provider for additional deployments
    k8s_provider = k8s.Provider(
        f"{prefix}-llm-k8s-provider",
        kubeconfig=default_stack.aks_cluster.kube_configs[0].raw_config,
        opts=pulumi.ResourceOptions(depends_on=[default_stack.aks_cluster])
    )
    
    # Deploy Chroma vector database
    chroma_release = helm.Release(
        "chroma",
        chart="chroma",
        repository_opts=helm.RepositoryOptsArgs(
            repo="https://amikos-tech.github.io/chromadb-chart/"
        ),
        namespace="default",
        values={
            "chroma": {
                "auth": {
                    "enabled": False  # Disable auth for simplicity, enable in production
                },
                "serverHttpPort": 8000,
                "dataVolumeSize": "10Gi",
                "logLevel": "INFO"
            },
            "service": {
                "type": "ClusterIP",
                "port": 8000
            },
            "persistence": {
                "enabled": True,
                "size": "10Gi",
                "storageClass": "default"
            },
            "resources": {
                "requests": {
                    "memory": "512Mi",
                    "cpu": "250m"
                },
                "limits": {
                    "memory": "2Gi",
                    "cpu": "1000m"
                }
            }
        },
        opts=pulumi.ResourceOptions(
            provider=k8s_provider,
            depends_on=[default_stack.aks_cluster]
        )
    )
    
    # Create a service to expose Chroma if needed
    chroma_service = k8s.core.v1.Service(
        "chroma-service",
        metadata=k8s.meta.v1.ObjectMetaArgs(
            name="chroma-db",
            namespace="default",
            labels={
                "app": "chroma",
                "component": "vector-database"
            }
        ),
        spec=k8s.core.v1.ServiceSpecArgs(
            selector={
                "app.kubernetes.io/name": "chroma"
            },
            ports=[
                k8s.core.v1.ServicePortArgs(
                    port=8000,
                    target_port=8000,
                    protocol="TCP",
                    name="http"
                )
            ],
            type="ClusterIP"
        ),
        opts=pulumi.ResourceOptions(
            provider=k8s_provider,
            depends_on=[chroma_release]
        )
    )
    
    return LLMStack(
        resource_group=default_stack.resource_group,
        aks_cluster=default_stack.aks_cluster,
        storage=default_stack.storage,
        zenml_storage=default_stack.zenml_storage,
        dvc_storage=default_stack.dvc_storage,
        acr=default_stack.acr,
        mlflow=default_stack.mlflow,
        zenserver=default_stack.zenserver,
        seldon=default_stack.seldon,
        chroma=ChromaDatabase(
            release=chroma_release,
            service_name=chroma_service.metadata.name
        )
    )