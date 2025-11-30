# Loist Music Library MCP Server Documentation

Welcome to the documentation for the Loist Music Library MCP Server. This central hub provides detailed information about the project's architecture, deployment, features, and development practices.

## 🚀 Getting Started

- **[Architecture Overview](architecture-overview.md)**: Start here for a high-level look at the system's components and design.
- **[Google Cloud Platform Overview](google-cloud-platform-overview.md)**: Understand the GCP services that power the application.
- **[Staging Environment Setup](staging-environment-setup.md)**: A guide to setting up and using the staging environment for testing.

## ☁️ Cloud Infrastructure & Deployment

A complete guide to the CI/CD pipeline, deployment process, and cloud service configuration.

- **CI/CD & Deployment:**
  - **[Google Cloud Build Setup](google-cloud-build-setup.md)**: How to set up and configure the CI/CD pipeline.
  - **[Cloud Build Triggers](cloud-build-triggers.md)**: Configuration for automated build triggers.
  - **[Cloud Run Automated Deployment](cloud-run-deployment.md)**: The end-to-end deployment process to Cloud Run.
  - **[Migration from GitHub Actions](github-actions-to-cloud-build-migration.md)**: History and reasoning for the move to Google Cloud Build.
- **Validation & Rollback:**
  - **[Deployment Validation Guide](deployment-validation-guide.md)**: How to validate a new deployment.
  - **[Deployment Validation Results](deployment-validation-results.md)**: A log of recent validation outcomes.
  - **[Deployment Rollback Procedure](deployment-rollback-procedure.md)**: Steps to take if a rollback is needed.
  - **[Troubleshooting Deployment](troubleshooting-deployment.md)**: Common deployment issues and their solutions.
- **Services & Configuration:**
  - **[GCP Service Account Setup](gcp-service-account-setup.md)**: Guide for setting up the necessary service accounts.
  - **[GCS Organization Structure](gcs-organization-structure.md)**: How audio files and assets are stored in Google Cloud Storage.
  - **[Cloud SQL Cost Analysis](cloud-sql-cost-analysis.md)**: Analysis and optimization strategies for database costs.
  - **[PostgreSQL Performance Configuration](research-postgresql-cloud-sql-options.md)**: Research and configuration for database performance.
  - **[Custom Domain Mapping Guide](custom-domain-mapping-guide.md)**: How to map a custom domain to the Cloud Run services.
  - **[GCP Containers Audit Report](gcp-containers-audit-report.md)**: An audit of running container instances.

## 🛠️ API & Endpoints

Detailed documentation for the server's core functionalities.

- **Core MCP Tools:**
  - **[MCP Testing Guide](mcp-testing-guide.md)**: A guide to testing the available MCP tools.
  - **[process_audio_complete API](process-audio-complete-api.md)**: API for the main audio ingestion and processing tool.
  - **[Query Tools API](query-tools-api.md)**: Documentation for `get_audio_metadata`, `search_library`, and `delete_audio`.
  - **[MCP Resources API](mcp-resources-api.md)**: Details on accessing stream, metadata, and thumbnail resources.
- **Feature-Specific APIs:**
  - **[Download Endpoint API](download-endpoint-api.md)**: Complete API documentation for audio download with format conversion.
  - **[Download Endpoint Investigation](download-endpoint-investigation.md)**: Technical design details for the download endpoint.
  - **[Edit Metadata Endpoint Investigation](edit-metadata-endpoint-investigation.md)**: The design for the metadata editing endpoint.
- **Frontend & Embeds:**
  - **[Frontend API Integration Guide](frontend-api-integration.md)**: Key endpoints and variables for frontend development.
  - **[Embed Player Guide](embed-player-guide.md)**: How to use the HTML5 audio embed player.
  - **[Enhanced Social Sharing](enhanced-social-sharing.md)**: Details on Open Graph, Twitter Cards, and other social features.
  - **[Iframe Embedding Troubleshooting](iframe-embedding-troubleshooting.md)**: Solutions for common iframe issues.
  - **[Embed Implementation Status](embed-implementation-status.md)**: Current status of the embed features.

## 💻 Development & Best Practices

Guides for developers contributing to the project.

- **Core Practices:**
  - **[Module Organization Guide](module-organization-guide.md)**: Principles for structuring code and modules.
  - **[Database Best Practices](database-best-practices.md)**: Guidelines for performance, transactions, and migrations.
  - **[Exception Handling Guide](exception-handling-guide.md)**: How to use the unified exception framework.
  - **[Reliability Features Guide](reliability-features-guide.md)**: Guide to using Circuit Breaker and Retry Logic.
- **Testing & Quality:**
  - **[Testing Practices Guide](testing-practices-guide.md)**: Overview of the comprehensive testing strategy.
  - **[Pre-PR Testing Guide](pre-pr-testing-guide.md)**: Local testing checklist before submitting a pull request.
  - **[Testing Metadata Generation](testing-metadata-generation.md)**: Specifics on testing social sharing tag generation.
- **Configuration:**
  - **[Environment Variables](environment-variables.md)**: A complete reference for all environment variables.
  - **[Environment Audit 2025](environment-audit-2025.md)**: An audit of the environment configuration against best practices.
  - **[Development Cost Optimization](development-cost-optimization.md)**: How to minimize cloud costs during development.

## 🔒 Security

Security analyses, procedures, and guides.

- **[Secret Rotation Guide](secret-rotation-guide.md)**: Procedures for rotating database passwords, bearer tokens, and other secrets.
- **[Security Scanning Guide](security-scanning.md)**: Information on the integrated security scanning tools (Bandit, Safety).
- **[Security Embed Analysis](security-embed-analysis.md)**: Analysis of the security of the public embed endpoint.

## 🔍 Fixes & Investigations

Documents related to specific bug fixes and technical investigations.

- **[MCP Tool Discovery Fix](mcp-tool-discovery-fix.md)**: How a bug preventing tool discovery in Cursor was resolved.
- **[Metadata Fallback Strategy](metadata-fallback-strategy.md)**: The strategy for handling audio files with missing metadata.
- **[Exception Serialization Improvements](exception-serialization-improvements.md)**: Fixes to prevent `NameError` during exception handling.
- **[Tech Debt Analysis](tech-debt-analysis.md)**: Analysis of technical debt related to reliability features.
- **[A2A Protocol Analysis](a2a-integration-analysis.md)**: An analysis document for integrating the A2A protocol.
- **[A2A MVP Implementation Tasks](a2a-mvp-implementation-tasks.md)**: A task list for the A2A protocol MVP.
