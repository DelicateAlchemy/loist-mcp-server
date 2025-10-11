# GitHub Actions Setup Guide

This guide explains how to configure GitHub Secrets required for the database provisioning workflow.

## Required GitHub Secrets

The following secrets must be configured in your GitHub repository before running the database provisioning workflow.

### 1. GCLOUD_SERVICE_KEY

The service account JSON key for authenticating with Google Cloud Platform.

**How to obtain:**

```bash
# Create a service account (if not already created)
gcloud iam service-accounts create github-actions \
    --display-name="GitHub Actions CI/CD" \
    --project=loist-music-library

# Grant necessary permissions
gcloud projects add-iam-policy-binding loist-music-library \
    --member="serviceAccount:github-actions@loist-music-library.iam.gserviceaccount.com" \
    --role="roles/cloudsql.admin"

# Create and download the key
gcloud iam service-accounts keys create github-actions-key.json \
    --iam-account=github-actions@loist-music-library.iam.gserviceaccount.com
```

**How to add to GitHub:**

1. Go to your GitHub repository
2. Navigate to **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Name: `GCLOUD_SERVICE_KEY`
5. Value: Copy the entire contents of `github-actions-key.json`
6. Click **Add secret**

**Security Note:** Delete the local key file after adding to GitHub:
```bash
rm github-actions-key.json
```

### 2. DB_USER

The database user for connecting to the Cloud SQL instance.

**Value:** `music_library_user` (or your configured database user)

**How to add:**
1. Go to **Settings** → **Secrets and variables** → **Actions**
2. Click **New repository secret**
3. Name: `DB_USER`
4. Value: `music_library_user`
5. Click **Add secret**

### 3. DB_PASSWORD

The password for the database user.

**How to obtain:**
```bash
# Retrieve from your .env.database file (created during provisioning)
cat .env.database | grep DB_PASSWORD
```

**How to add:**
1. Go to **Settings** → **Secrets and variables** → **Actions**
2. Click **New repository secret**
3. Name: `DB_PASSWORD`
4. Value: (paste the password from .env.database)
5. Click **Add secret**

## Workflow Configuration

The workflow uses the following environment variables (configured in the workflow file):

- `PROJECT_ID`: `loist-music-library`
- `REGION`: `us-central1`
- `INSTANCE_NAME`: `loist-music-library-db`
- `DATABASE_NAME`: `music_library`

## IAM Permissions Required

The service account used for GitHub Actions needs the following IAM roles:

1. **Cloud SQL Admin** (`roles/cloudsql.admin`)
   - Create and manage Cloud SQL instances
   - Manage database users and permissions

2. **Service Account User** (`roles/iam.serviceAccountUser`)
   - Use service accounts for authentication

3. **Storage Object Viewer** (`roles/storage.objectViewer`) *(if accessing GCS)*
   - Read objects from Cloud Storage buckets

### Granting Permissions

```bash
# Grant Cloud SQL Admin role
gcloud projects add-iam-policy-binding loist-music-library \
    --member="serviceAccount:github-actions@loist-music-library.iam.gserviceaccount.com" \
    --role="roles/cloudsql.admin"

# Grant Service Account User role
gcloud projects add-iam-policy-binding loist-music-library \
    --member="serviceAccount:github-actions@loist-music-library.iam.gserviceaccount.com" \
    --role="roles/iam.serviceAccountUser"

# Grant Storage Object Viewer role (if needed)
gcloud projects add-iam-policy-binding loist-music-library \
    --member="serviceAccount:github-actions@loist-music-library.iam.gserviceaccount.com" \
    --role="roles/storage.objectViewer"
```

## Workflow Actions

The workflow supports four actions via manual dispatch:

### 1. Provision

Creates a new Cloud SQL instance.

**Usage:**
1. Go to **Actions** tab in GitHub
2. Select **Database Provisioning** workflow
3. Click **Run workflow**
4. Select action: `provision`
5. Click **Run workflow**

### 2. Migrate

Runs database migrations against the Cloud SQL instance.

**Usage:**
1. Go to **Actions** tab
2. Select **Database Provisioning** workflow
3. Click **Run workflow**
4. Select action: `migrate`
5. Click **Run workflow**

**Automatic Trigger:** Also runs automatically on push to `main` branch.

### 3. Test

Runs database tests against the Cloud SQL instance.

**Usage:**
1. Go to **Actions** tab
2. Select **Database Provisioning** workflow
3. Click **Run workflow**
4. Select action: `test`
5. Click **Run workflow**

**Automatic Trigger:** Also runs automatically on pull requests that modify database files.

### 4. Health Check

Verifies the Cloud SQL instance is healthy and accessible.

**Usage:**
1. Go to **Actions** tab
2. Select **Database Provisioning** workflow
3. Click **Run workflow**
4. Select action: `health-check`
5. Click **Run workflow**

## Automatic Triggers

The workflow automatically runs in the following scenarios:

### On Push to main/dev branches
- **Condition:** Changes to `database/**` or provisioning scripts
- **Action:** Runs migration job

### On Pull Request
- **Condition:** Changes to `database/**` or provisioning scripts
- **Action:** Runs test job

## Troubleshooting

### Authentication Error: "Unable to read file"

**Symptom:**
```
ERROR: (gcloud.auth.activate-service-account) Unable to read file []: [Errno 2] No such file or directory: ''
```

**Solution:**
Ensure `GCLOUD_SERVICE_KEY` secret is properly configured with the complete JSON content.

### Database Connection Failed

**Symptom:**
```
❌ Database connection failed: could not connect to server
```

**Solutions:**
1. Verify `DB_USER` and `DB_PASSWORD` secrets are correct
2. Ensure Cloud SQL instance is running
3. Check that Cloud SQL Proxy started successfully
4. Verify service account has Cloud SQL Client permissions

### Instance Already Exists

**Symptom:**
```
ERROR: (gcloud.sql.instances.create) HTTPError 409: The Cloud SQL instance already exists.
```

**Solution:**
This is expected behavior. The workflow checks for existing instances and skips provisioning if found.

### Permission Denied Errors

**Symptom:**
```
ERROR: (gcloud.sql.instances.create) HTTPError 403: The caller does not have permission
```

**Solution:**
Verify the service account has the required IAM roles (see "IAM Permissions Required" section above).

## Security Best Practices

1. **Never commit service account keys** to version control
2. **Use GitHub Secrets** for all sensitive data
3. **Rotate service account keys** regularly (every 90 days)
4. **Use least privilege** - grant only necessary IAM roles
5. **Enable deletion protection** on production Cloud SQL instances
6. **Use Cloud SQL Proxy** for secure connections
7. **Monitor workflow logs** for suspicious activity
8. **Audit IAM permissions** regularly

## Verification

After setting up secrets, verify the configuration:

1. Run the health-check workflow action
2. Check the workflow logs for successful authentication
3. Verify database connection succeeds

Expected output:
```
✅ Database connection successful!
PostgreSQL version: PostgreSQL 15.x on x86_64-pc-linux-gnu...
```

## Additional Resources

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Google Cloud SQL Documentation](https://cloud.google.com/sql/docs)
- [Cloud SQL Proxy Documentation](https://cloud.google.com/sql/docs/postgres/sql-proxy)
- [IAM Service Accounts](https://cloud.google.com/iam/docs/service-accounts)


