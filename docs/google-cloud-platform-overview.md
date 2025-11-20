# Google Cloud Platform Overview

This document provides a comprehensive overview of the Google Cloud Platform infrastructure and services used by the Loist Music Library MCP Server.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Google Cloud Platform                    │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐    ┌──────────────┐    ┌─────────────────┐ │
│  │ Cloud Build │───▶│  Artifact    │───▶│   Cloud Run     │ │
│  │   CI/CD     │    │  Registry    │    │ (Serverless)    │ │
│  └─────────────┘    └──────────────┘    └─────────────────┘ │
│                                                ▲             │
│  ┌─────────────┐    ┌──────────────┐         │             │
│  │   Cloud     │    │    Secret    │         │             │
│  │    SQL      │◀───┤   Manager    │◀────────┘             │
│  │(PostgreSQL) │    │              │                       │
│  └─────────────┘    └──────────────┘                       │
│                                                             │
│  ┌─────────────┐    ┌──────────────┐                       │
│  │   Cloud     │    │     IAM      │                       │
│  │  Storage    │◀───┤  SignBlob    │◀──────────────────────┘
│  │   (GCS)     │    │    API       │
│  └─────────────┘    └──────────────┘
└─────────────────────────────────────────────────────────────┘
```

## Core Services

### 🏗️ **Cloud Build** - CI/CD Pipeline
**Purpose**: Automated build, test, and deployment pipeline

**Key Features**:
- Multi-stage testing (unit, integration, MCP validation)
- Automated vulnerability scanning
- Docker image building and optimization
- Production and staging deployment

**Documentation**:
- [Cloud Build Setup Guide](google-cloud-build-setup.md) - Initial setup and configuration
- [Cloud Build CI/CD Setup](cloud-build-ci-cd-setup.md) - Pipeline architecture and workflows
- [Cloud Build Triggers](cloud-build-triggers.md) - Trigger configuration and management

### 🚀 **Cloud Run** - Serverless Container Platform
**Purpose**: Scalable, serverless container deployment

**Key Features**:
- Auto-scaling based on traffic
- Built-in load balancing and SSL termination
- Health checks and zero-downtime deployments
- Environment-specific configurations

**Documentation**:
- [Cloud Run Deployment](cloud-run-deployment.md) - Complete deployment guide
- [Custom Domain Mapping Guide](custom-domain-mapping-guide.md) - HTTPS and custom domains
- [Environment Variables](environment-variables.md) - Configuration reference

### 🗄️ **Cloud SQL** - Managed PostgreSQL Database
**Purpose**: Reliable, managed PostgreSQL database service

**Key Features**:
- Automatic backups and high availability
- Connection pooling optimization
- Performance monitoring and alerting
- Secure private networking

**Documentation**:
- [Cloud SQL Cost Analysis](cloud-sql-cost-analysis.md) - Cost optimization strategies
- [PostgreSQL Performance Configuration](postgresql-performance-configuration.md) - Performance tuning
- [Research: PostgreSQL Cloud SQL Options](research-postgresql-cloud-sql-options.md) - Architecture decisions

### ☁️ **Cloud Storage** - Object Storage
**Purpose**: Scalable object storage with IAM-based access control

**Key Features**:
- Signed URL generation for secure access
- Global CDN integration capabilities
- Lifecycle management and cost optimization
- IAM SignBlob API for secure URL generation

**Documentation**:
- [GCS Organization Structure](gcs-organization-structure.md) - Storage organization and naming

### 🔐 **Security & Identity**
**Purpose**: Secure authentication, authorization, and secret management

**Key Features**:
- Service account management and IAM roles
- Secret Manager for sensitive configuration
- Secure credential rotation and access control

**Documentation**:
- [GCP Service Account Setup](gcp-service-account-setup.md) - Service account creation and IAM
- [Secret Rotation Guide](secret-rotation-guide.md) - Secret management and rotation

## Deployment Environments

### Production Environment (`main` branch)
- **Trigger**: Push to `main` branch → `cloudbuild.yaml`
- **Services**: Full production deployment with strict quality gates
- **Testing**: 75% unit coverage, 70% database coverage, blocking failures
- **Monitoring**: Full production monitoring and alerting

### Staging Environment (`dev` branch)
- **Trigger**: Push to `dev` branch → `cloudbuild-staging.yaml`
- **Services**: Full staging deployment with relaxed quality gates
- **Testing**: 65% unit coverage, 60% database coverage, warning-only failures
- **Purpose**: Pre-production validation and testing

## Development Workflow

### Local Development
```bash
# Start local development environment
docker-compose up -d

# Run tests locally
pytest tests/ -v
```

### CI/CD Pipeline
```bash
# Push to dev branch triggers staging deployment
git checkout dev
git push origin dev

# Push to main branch triggers production deployment
git checkout main
git merge dev
git push origin main
```

## Cost Optimization

### Current Cost Structure
- **Cloud Build**: 2,500 free build minutes/month
- **Cloud Run**: Pay-per-use with generous free tier
- **Cloud SQL**: ~$50-80/month (can be stopped when not needed)
- **Cloud Storage**: Pay-per-GB with lifecycle policies

### Optimization Strategies
- [Cloud SQL Cost Optimization](cloud-sql-cost-analysis.md) - Database cost management
- Stop Cloud SQL during development phases
- Use Cloud Build free tier efficiently
- Implement storage lifecycle policies

## Migration History

### From GitHub Actions to Cloud Build
- **Completed**: November 2025
- **Benefits**: Simplified IAM, faster builds, better security
- **Documentation**: [GitHub Actions to Cloud Build Migration](github-actions-to-cloud-build-migration.md)

## Monitoring & Troubleshooting

### Key Monitoring Points
- Cloud Build execution logs
- Cloud Run service health and metrics
- Cloud SQL performance and connections
- Application logs and error tracking

### Common Issues
- [Deployment Validation Guide](deployment-validation-guide.md) - Deployment troubleshooting
- [Troubleshooting Deployment](troubleshooting-deployment.md) - Common deployment issues
- [Deployment Rollback Procedure](deployment-rollback-procedure.md) - Rollback procedures

## Security Considerations

### Authentication & Authorization
- Service accounts with minimal required permissions
- Secret Manager for sensitive configuration
- IAM roles following principle of least privilege

### Network Security
- Private Cloud SQL instances
- VPC Service Controls where applicable
- Secure communication between services

## Quick Reference

### Service URLs
- **Production**: https://music-library-mcp-123456789.us-central1.run.app
- **Staging**: https://music-library-mcp-staging-123456789.us-central1.run.app
- **Cloud Console**: https://console.cloud.google.com

### Key Commands
```bash
# Check Cloud Build status
gcloud builds list --limit=5

# Check Cloud Run services
gcloud run services list

# Check Cloud SQL instances
gcloud sql instances list

# View recent deployments
gcloud run revisions list --service=music-library-mcp
```

### Environment Variables
- [Complete Environment Variables Reference](environment-variables.md)
- [Environment Audit](environment-audit-2025.md)

---

**This document serves as the main entry point for all Google Cloud Platform documentation. Individual service details are covered in the linked documents above.**
