# GCP Service Account Setup Guide

## 🚀 Quick Start (5 minutes)

Follow these steps to create and configure GCP service accounts for automated deployments.

---

## Step 1: Create Service Account & Key

```bash
# 1. Create service account
gcloud iam service-accounts create github-actions \
    --display-name="GitHub Actions CI/CD" \
    --project=loist-music-library

# 2. Grant Cloud SQL Admin role
gcloud projects add-iam-policy-binding loist-music-library \
    --member="serviceAccount:github-actions@loist-music-library.iam.gserviceaccount.com" \
    --role="roles/cloudsql.admin"

# 3. Create and download key
gcloud iam service-accounts keys create github-actions-key.json \
    --iam-account=github-actions@loist-music-library.iam.gserviceaccount.com

# ✅ Key created: github-actions-key.json
```

---

## Step 2: Store Service Account Key

### For Cloud Build / CI/CD Systems

Store the service account key as a secret in your CI/CD system:

**GitHub Actions (if still used):**
1. Open `service-account-key.json` and copy entire contents
2. Go to: **GitHub Repo** → **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Name: `GCLOUD_SERVICE_KEY`
5. Paste the JSON content
6. Click **Add secret**

**Google Cloud Secret Manager (recommended):**
```bash
# Create secret in Secret Manager
echo -n "$(cat service-account-key.json)" | \
gcloud secrets create service-account-key --data-file=-
```

### DB_USER

1. Click **New repository secret**
2. Name: `DB_USER`
3. Value: `music_library_user`
4. Click **Add secret**

### DB_PASSWORD

```bash
# Get password from your .env.database file
cat .env.database | grep DB_PASSWORD
```

1. Click **New repository secret**
2. Name: `DB_PASSWORD`
3. Paste the password value
4. Click **Add secret**

---

## Step 3: Verify Setup

Test the service account authentication:

```bash
# Test authentication with the key
gcloud auth activate-service-account --key-file=service-account-key.json
gcloud config set project loist-music-library

# Test Cloud SQL access
gcloud sql instances list
```

### Expected Output ✅
```
NAME                     DATABASE_VERSION  LOCATION        TIER              PRIMARY_ADDRESS    STATUS
loist-music-library-db   POSTGRES_15       us-central1      db-f1-micro       34.102.xxx.xxx     RUNNABLE
```

---

## Step 4: Clean Up Local Files

```bash
# Delete the local key file (it's now stored securely)
rm service-account-key.json

# Verify it's gone
ls -la service-account-key.json
# Should show: No such file or directory
```

**Security Note:** Never commit service account keys to version control. Always store them in Secret Manager or CI/CD secrets.

---

## 📋 Secrets Checklist

- [ ] `GCLOUD_SERVICE_KEY` - Service account JSON
- [ ] `DB_USER` - Database username
- [ ] `DB_PASSWORD` - Database password
- [ ] Verified with health-check workflow
- [ ] Deleted local key file

---

## 🔧 Troubleshooting

### "Unable to read file []"
- **Solution:** Check that `GCLOUD_SERVICE_KEY` contains the full JSON (starts with `{` and ends with `}`)

### "Permission denied" 
- **Solution:** Grant Cloud SQL Admin role:
  ```bash
  gcloud projects add-iam-policy-binding loist-music-library \
      --member="serviceAccount:github-actions@loist-music-library.iam.gserviceaccount.com" \
      --role="roles/cloudsql.admin"
  ```

### "Connection failed"
- **Solution:** Verify `DB_USER` and `DB_PASSWORD` match your `.env.database`

---

## 📚 Related Documentation

For CI/CD setup, see:
- [Cloud Build Setup Guide](./google-cloud-build-setup.md)
- [Cloud Build Triggers](./cloud-build-triggers.md)
- [Secret Manager Guide](./secret-rotation-guide.md)

---

## ⚡ Quick Verification Commands

```bash
# Verify service account has required roles
gcloud iam service-accounts get-iam-policy service-account@project.iam.gserviceaccount.com

# Test Cloud SQL permissions
gcloud sql instances describe instance-name --project=project-id

# List all service accounts
gcloud iam service-accounts list
```

---

**Done! 🎉** Your GitHub Actions workflow is now configured for database provisioning.


