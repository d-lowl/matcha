# Matcha ML Infrastructure (Pulumi)

This directory contains the Pulumi-based infrastructure as code for Matcha ML, providing a modern, type-safe alternative to Terraform.

## Quick Start

### Prerequisites

1. **Install Pulumi**
   ```bash
   curl -fsSL https://get.pulumi.com | sh
   export PATH=$PATH:$HOME/.pulumi/bin
   ```

2. **Install Poetry**
   ```bash
   curl -sSL https://install.python-poetry.org | python3 -
   export PATH="$HOME/.local/bin:$PATH"
   ```

3. **Azure CLI Setup**
   ```bash
   az login
   az account set --subscription <your-subscription-id>
   ```

### Deployment

#### Option 1: Using the Deployment Script (Recommended)

```bash
# Deploy remote state storage first (required)
python3 deploy.py deploy remote_state_storage

# Deploy main MLOps infrastructure
python3 deploy.py deploy default

# Or deploy LLM-enhanced infrastructure
python3 deploy.py deploy llm
```

#### Option 2: Manual Pulumi Commands

```bash
# Set up Pulumi project in .matcha directory
python3 deploy.py deploy remote_state_storage --auto-approve

# Navigate to project directory
cd .matcha/infrastructure/pulumi

# Install dependencies
poetry install

# Configure stack
pulumi config set azure-native:location "East US"
pulumi config set matcha-ml:prefix "your-prefix"
pulumi config set --secret matcha-ml:password "your-password"

# Deploy
MATCHA_COMPONENT=default pulumi up
```

## Components

### 1. Remote State Storage
**Purpose**: Creates Azure storage for Pulumi state management

**Resources**:
- Resource Group
- Storage Account (LRS)
- Blob Container

**Usage**:
```bash
python3 deploy.py deploy remote_state_storage
```

### 2. Default Stack
**Purpose**: Main MLOps platform infrastructure

**Resources**:
- Azure Kubernetes Service (AKS) with auto-scaling
- Storage Accounts (general, ZenML, DVC)  
- Azure Container Registry (ACR)
- MLflow (experiment tracking)
- ZenML Server (ML pipeline orchestration)
- Seldon Core (model serving)

**Usage**:
```bash
python3 deploy.py deploy default
```

### 3. LLM Stack
**Purpose**: Enhanced MLOps platform for LLM workloads

**Additional Resources**:
- Chroma vector database
- LLM-optimized configurations

**Usage**:
```bash
python3 deploy.py deploy llm
```

## Configuration

### Stack Configuration File: `Pulumi.dev.yaml`

```yaml
config:
  azure-native:location: "East US"
  matcha-ml:prefix: "matcha"
  matcha-ml:component: "default"
  matcha-ml:username: "admin"
  matcha-ml:password:
    secure: "encrypted-password"
  matcha-ml:zenmlserver_version: "latest"
  matcha-ml:seldon_name: "seldon"
  matcha-ml:seldon_namespace: "seldon-system"
```

### Setting Secrets

```bash
# Set sensitive configuration values
pulumi config set --secret matcha-ml:password "your-secure-password"
```

### Multi-Environment Setup

```bash
# Create production stack
pulumi stack init production
pulumi config set azure-native:location "West Europe"
pulumi config set matcha-ml:prefix "matcha-prod"

# Switch between stacks
pulumi stack select dev
pulumi stack select production
```

## Project Structure

```
.
├── components/
│   ├── __init__.py
│   ├── remote_state_storage.py    # Azure storage for state
│   ├── default_stack.py           # Main MLOps infrastructure
│   └── llm_stack.py              # LLM-enhanced stack
├── pyproject-pulumi.toml          # Poetry dependencies
├── Pulumi.yaml                    # Main project config
├── Pulumi.dev.yaml               # Dev stack config
├── __main__.py                   # Main Pulumi program
└── deploy.py                     # Deployment script
```

## Development

### Adding New Resources

1. **Extend existing components**:
   ```python
   # In components/default_stack.py
   def create_default_stack(...):
       # Add new Azure resources
       new_resource = azure.service.Resource(...)
       return DefaultStack(..., new_resource=new_resource)
   ```

2. **Create new components**:
   ```python
   # Create components/new_component.py
   def create_new_component(prefix: str, location: str, config: pulumi.Config):
       # Implementation
       return NewComponent(...)
   ```

3. **Update main program**:
   ```python
   # In __main__.py
   elif component == "new_component":
       stack = new_component.create_new_component(...)
   ```

### Testing

```bash
# Run unit tests
export PYTHONPATH=/workspace/src
python3 -m pytest tests/test_services/test_pulumi_service.py -v

# Test deployment (dry run)
python3 deploy.py deploy default --stack test
pulumi preview --diff
```

### Debugging

```bash
# Enable verbose logging
export PULUMI_DEBUG=true
export PULUMI_LOG_LEVEL=debug

# Run deployment
python3 deploy.py deploy default
```

## State Management

### Using Azure Backend

```bash
# Configure Azure blob storage backend
pulumi login azblob://mystatecontainer
```

### Local State (Development)

```bash
# Use local state file (default)
pulumi login --local
```

### State Operations

```bash
# View current state
pulumi stack output --json

# Export state
pulumi stack export > stack-state.json

# Import state
pulumi stack import < stack-state.json
```

## Troubleshooting

### Common Issues

1. **Azure Authentication Errors**
   ```bash
   az login --tenant <tenant-id>
   az account set --subscription <subscription-id>
   ```

2. **Resource Naming Conflicts**
   - Update the `prefix` configuration to use unique names
   - Check for existing resources in Azure portal

3. **Poetry Installation Issues**
   ```bash
   # Reinstall Poetry
   curl -sSL https://install.python-poetry.org | python3 - --uninstall
   curl -sSL https://install.python-poetry.org | python3 -
   ```

4. **Stack State Conflicts**
   ```bash
   pulumi stack ls
   pulumi stack select <correct-stack>
   pulumi refresh  # Sync state with actual resources
   ```

### Getting Help

1. **View stack information**:
   ```bash
   pulumi stack ls
   pulumi stack output
   pulumi stack history
   ```

2. **Resource information**:
   ```bash
   pulumi logs
   pulumi stack graph | dot -Tpng -o stack.png
   ```

3. **Pulumi documentation**: https://www.pulumi.com/docs/

## Migration from Terraform

If you're migrating from the previous Terraform setup, see the [migration guide](docs/TERRAFORM_TO_PULUMI_MIGRATION.md) for detailed instructions.

Key differences:
- **Type Safety**: Full Python type hints
- **Better Integration**: Native Python vs. subprocess calls
- **Enhanced Testing**: Comprehensive unit test coverage
- **Improved Error Handling**: Clear, actionable error messages

## Contributing

1. **Code Style**: Follow existing patterns and type hints
2. **Testing**: Add tests for new components
3. **Documentation**: Update this README and component docstrings
4. **Validation**: Run tests and deployment validation before submitting

## Performance

Typical deployment times:
- **Remote State Storage**: ~2 minutes
- **Default Stack**: ~10-12 minutes  
- **LLM Stack**: ~15-18 minutes

Resource creation is parallelized where possible for optimal performance.