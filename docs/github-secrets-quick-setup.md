# GitHub Secrets Quick Setup

## 🚀 Quick Start (5 minutes)

Follow these steps to configure GitHub Secrets for database provisioning workflow.

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

## Step 2: Add Secrets to GitHub

### GCLOUD_SERVICE_KEY

1. Open `github-actions-key.json` and copy entire contents
2. Go to: **GitHub Repo** → **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Name: `GCLOUD_SERVICE_KEY`
5. Paste the JSON content
6. Click **Add secret**

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

1. Go to **Actions** tab in GitHub
2. Select **Database Provisioning** workflow
3. Click **Run workflow**
4. Choose action: `health-check`
5. Click **Run workflow**

### Expected Output ✅
```
✅ Database connection successful!
PostgreSQL version: PostgreSQL 15.x...
```

---

## Step 4: Clean Up Local Files

```bash
# Delete the local key file (it's now in GitHub Secrets)
rm github-actions-key.json

# Verify it's gone
ls -la github-actions-key.json
# Should show: No such file or directory
```

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

## 📚 Full Documentation

For detailed information, see: [GitHub Actions Setup Guide](./github-actions-setup.md)

---

## 🎯 Available Workflow Actions

| Action | Description | When to Use |
|--------|-------------|-------------|
| `provision` | Create Cloud SQL instance | Initial setup |
| `migrate` | Run database migrations | After schema changes |
| `test` | Run database tests | Before merging code |
| `health-check` | Verify instance health | Troubleshooting |

---

## ⚡ One-Liner Verification

```bash
# Verify all secrets are set in GitHub (requires gh CLI)
gh secret list
```

Expected output:
```
GCLOUD_SERVICE_KEY  Updated YYYY-MM-DD
DB_USER            Updated YYYY-MM-DD
DB_PASSWORD        Updated YYYY-MM-DD
```

---

**Done! 🎉** Your GitHub Actions workflow is now configured for database provisioning.


