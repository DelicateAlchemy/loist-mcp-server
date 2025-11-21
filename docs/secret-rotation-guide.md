# Secret Rotation Guide for Loist Music Library MCP Server

This guide provides comprehensive documentation for implementing secret rotation policies in the Loist Music Library MCP Server deployment.

## Overview

Secret rotation is a critical security practice that limits the impact of potential secret compromise by regularly updating credentials and invalidating old values. This guide covers rotation strategies, automation, and operational procedures for the MCP server.

## Secret Types and Rotation Strategies

### 1. Database Passwords
**Rotation Frequency**: Quarterly or when personnel changes occur
**Impact**: High - requires coordinated database and application updates
**Automation Level**: Semi-automated with manual oversight

### 2. Bearer Tokens
**Rotation Frequency**: Monthly or bi-monthly
**Impact**: Medium - requires client reconfiguration
**Automation Level**: Fully automated

### 3. API Keys (Future)
**Rotation Frequency**: Monthly
**Impact**: Medium - requires external service updates
**Automation Level**: Semi-automated

### 4. GCS Service Account Keys (Alternative)
**Rotation Frequency**: As needed or annually
**Impact**: Low - handled by Google Cloud IAM
**Automation Level**: Google Cloud managed

## Automated Rotation Architecture

### Pub/Sub-Based Rotation System

Google Cloud Secret Manager supports automated rotation through Pub/Sub notifications sent to designated topics when secrets reach their rotation schedule.

#### Rotation Service Implementation

```yaml
# Example Cloud Run service for handling rotation
apiVersion: serving.knative.dev/v1
kind: Service
metadata:
  name: secret-rotation-service
spec:
  template:
    spec:
      containers:
      - image: gcr.io/your-project/rotation-service
        env:
        - name: ROTATION_TOPIC
          value: projects/your-project/topics/secret-rotation
        - name: DATABASE_INSTANCE
          value: your-database-instance
```

#### Rotation Workflow

1. **Trigger**: Secret Manager sends `SECRET_ROTATE` message to Pub/Sub topic
2. **Processing**: Rotation service receives message and identifies secret type
3. **External Updates**: Service updates external systems (database, APIs)
4. **Secret Creation**: New secret version created in Secret Manager
5. **Validation**: Service validates new credentials work correctly
6. **Notification**: Success/failure notifications sent to monitoring systems

### Database Password Rotation

```python
# Example rotation handler for database passwords
import os
from google.cloud import secretmanager
from google.cloud import sql

def rotate_database_password(event, context):
    """Handle database password rotation."""

    # Parse Pub/Sub message
    secret_name = event['attributes']['secretId']

    # Get current secret
    client = secretmanager.SecretManagerServiceClient()
    secret_path = client.secret_path(PROJECT_ID, secret_name)
    secret = client.get_secret(request={"name": secret_path})

    # Generate new password
    new_password = generate_secure_password()

    # Update database user
    sql_client = sql.Client()
    instance = sql_client.instance(DATABASE_INSTANCE)
    user = instance.user(APP_USER)
    user.update(password=new_password)

    # Create new secret version
    payload = new_password.encode('UTF-8')
    response = client.add_secret_version(
        request={
            "parent": secret_path,
            "payload": {"data": payload}
        }
    )

    # Update secret labels
    client.update_secret(
        request={
            "secret": {
                "name": secret_path,
                "labels": {"rotation": "completed", "version": response.name}
            }
        }
    )

    return f"Rotated password for {secret_name}"
```

## Manual Rotation Procedures

### Bearer Token Rotation

1. **Generate New Token**:
   ```bash
   NEW_TOKEN=$(openssl rand -base64 64 | tr -d "=+/" | cut -c1-64)
   ```

2. **Create New Secret Version**:
   ```bash
   echo -n "$NEW_TOKEN" | gcloud secrets versions add mcp-bearer-token --data-file=-
   ```

3. **Update Client Configurations**:
   - Update any hardcoded client configurations
   - Notify client application owners
   - Update documentation with new token format

4. **Disable Old Versions** (after grace period):
   ```bash
   gcloud secrets versions describe VERSION_ID --secret=mcp-bearer-token
   gcloud secrets versions disable VERSION_ID --secret=mcp-bearer-token
   ```

### Database Password Rotation

1. **Backup Current Configuration**:
   ```bash
   # Export current secret for rollback purposes
   gcloud secrets versions access latest --secret=db-password > backup_password.txt
   ```

2. **Generate New Password**:
   ```bash
   NEW_DB_PASSWORD=$(openssl rand -base64 32)
   ```

3. **Update Database User**:
   ```bash
   gcloud sql users set-password music_library_user \
     --instance=loist-music-library-db \
     --password="$NEW_DB_PASSWORD"
   ```

4. **Create New Secret Version**:
   ```bash
   echo -n "$NEW_DB_PASSWORD" | gcloud secrets versions add db-password --data-file=-
   ```

5. **Deploy Updated Application**:
   ```bash
   # Trigger deployment to use new password
   gcloud builds submit --config cloudbuild.yaml
   ```

6. **Verify Application Health**:
   ```bash
   curl -H "Authorization: Bearer $NEW_TOKEN" https://your-service-url/mcp/health
   ```

7. **Clean Up Old Versions** (after verification):
   ```bash
   # List versions
   gcloud secrets versions list db-password --filter="state:ENABLED"

   # Disable old versions (keep 2-3 recent versions)
   gcloud secrets versions disable OLD_VERSION_ID --secret=db-password
   ```

## Rotation Scheduling and Monitoring

### Automated Scheduling

Configure rotation schedules using Terraform:

```hcl
resource "google_secret_manager_secret" "bearer_token" {
  secret_id = "mcp-bearer-token"

  rotation {
    next_rotation_time = "2025-02-01T00:00:00Z"
    rotation_period    = "2592000s"  # 30 days
  }

  topics {
    name = google_pubsub_topic.rotation_topic.id
  }
}
```

### Monitoring and Alerting

Set up Cloud Monitoring alerts for rotation events:

```yaml
# Alert on rotation failures
alertPolicies:
- displayName: Secret Rotation Failure
  conditions:
  - displayName: Pub/Sub message age > 1 hour
    conditionThreshold:
      filter: resource.type=pubsub_subscription AND resource.labels.subscription_id=rotation-subscription
      duration: 3600s
      comparison: COMPARISON_GT
      thresholdValue: 3600

# Alert on secret access anomalies
- displayName: Unusual Secret Access
  conditions:
  - displayName: Rate of secret access > normal
    conditionThreshold:
      filter: resource.type=secretmanager.googleapis.com/Secret AND metric.type=secretmanager.googleapis.com/secret/access_count
      duration: 3600s
      comparison: COMPARISON_GT
      thresholdValue: 100  # Adjust based on normal usage
```

## Gradual Rollout Strategy

### Blue-Green Deployment for Secret Rotation

1. **Deploy New Version**: Deploy application with new secrets to separate Cloud Run service
2. **Traffic Splitting**: Route small percentage of traffic to new version
3. **Monitoring**: Monitor error rates and performance metrics
4. **Gradual Migration**: Increase traffic to new version if metrics are healthy
5. **Full Cutover**: Route 100% traffic to new version
6. **Cleanup**: Remove old Cloud Run service after verification

### Rollback Procedures

1. **Immediate Rollback**: If critical issues detected, immediately route traffic back
2. **Version Pinning**: Temporarily pin application to known-good secret version
3. **Investigation**: Analyze logs and metrics to identify root cause
4. **Fix and Redeploy**: Address issues and redeploy with corrected configuration

## Security Considerations

### Rotation Frequency Guidelines

- **High-Value Secrets** (database passwords, private keys): 30-90 days
- **Medium-Value Secrets** (API tokens, bearer tokens): 30-60 days
- **Low-Value Secrets** (public keys, certificates): 90-365 days

### Access Control During Rotation

- **Principle of Least Privilege**: Rotation service should only have permissions needed for rotation
- **Separate Service Account**: Use dedicated service account for rotation operations
- **Audit Logging**: All rotation activities logged and monitored
- **Approval Workflows**: For manual rotations, require approval from security team

### Incident Response

1. **Detection**: Monitor for unusual secret access patterns
2. **Containment**: Immediately rotate compromised secrets
3. **Investigation**: Analyze access logs to understand breach scope
4. **Recovery**: Update all affected systems with new credentials
5. **Lessons Learned**: Update rotation policies based on incident analysis

## Operational Best Practices

### Documentation Requirements

- **Runbooks**: Detailed procedures for each rotation type
- **Contact Lists**: Who to notify for different rotation scenarios
- **Rollback Plans**: How to revert changes if rotation fails
- **Testing Procedures**: How to validate rotated credentials

### Testing Rotation

1. **Unit Tests**: Test rotation logic with mocked external systems
2. **Integration Tests**: Test end-to-end rotation in staging environment
3. **Load Tests**: Verify rotation doesn't impact application performance
4. **Failure Tests**: Test rotation rollback procedures

### Compliance and Auditing

- **Audit Trails**: All rotation activities logged with timestamps
- **Compliance Reports**: Regular reports on rotation compliance
- **Change Management**: Rotation events tracked in change management system
- **Regulatory Requirements**: Meet requirements for credential management

## Implementation Checklist

### Planning Phase
- [ ] Identify all secrets requiring rotation
- [ ] Define rotation frequencies for each secret type
- [ ] Design rotation automation architecture
- [ ] Plan testing and validation procedures

### Implementation Phase
- [ ] Create rotation service and Pub/Sub topics
- [ ] Implement rotation handlers for each secret type
- [ ] Configure monitoring and alerting
- [ ] Test rotation procedures in staging

### Operational Phase
- [ ] Schedule regular rotation reviews
- [ ] Monitor rotation success/failure rates
- [ ] Update procedures based on lessons learned
- [ ] Maintain rotation compliance documentation

---

## Quick Reference

### Commands

```bash
# Check secret rotation status
gcloud secrets describe SECRET_NAME --format="value(rotation.nextRotationTime)"

# Manually trigger rotation (for testing)
gcloud secrets update SECRET_NAME --update-rotation-schedule="next-rotation-time=2025-01-01T00:00:00Z"

# List secret versions
gcloud secrets versions list SECRET_NAME

# Access specific version
gcloud secrets versions access VERSION_ID --secret=SECRET_NAME
```

### Monitoring Queries

```sql
-- Recent secret access
SELECT
  timestamp,
  resource.labels.secret_id,
  protopayload_auditlog.authentication_info.principalEmail
FROM `your-project.global._Default._Default`
WHERE
  resource.type = "secretmanager.googleapis.com/Secret"
  AND operation.last = true
ORDER BY timestamp DESC
LIMIT 100
```

This guide provides a comprehensive framework for implementing secret rotation in production environments. Regular rotation, combined with proper monitoring and testing, significantly reduces the risk of credential-based security incidents.
