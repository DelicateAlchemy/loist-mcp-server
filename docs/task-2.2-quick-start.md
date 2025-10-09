# Task 2.2 Quick Start Guide: PostgreSQL Database Provisioning

## 🚀 Quick Start

To create the Google Cloud SQL PostgreSQL instance for the MCP Music Library Server, run:

```bash
# From the project root directory
./scripts/execute-task-2.2.sh
```

This script will automatically:
1. Set up Google Cloud environment
2. Create Cloud SQL PostgreSQL instance
3. Configure database settings
4. Test the connection
5. Create documentation

## 📋 Prerequisites

### Required Software
- **Google Cloud CLI**: [Install gcloud](https://cloud.google.com/sdk/docs/install)
- **Bash**: Available on macOS, Linux, and Windows (WSL)

### Required Access
- Google Cloud Project with billing enabled
- Project Owner or Editor permissions
- Ability to create service accounts and assign roles

## 🔧 Manual Setup (Alternative)

If you prefer to run the steps manually:

### Step 1: Google Cloud Setup
```bash
# Set your project ID
export GCP_PROJECT_ID="your-project-id"

# Run Google Cloud setup
./scripts/setup-gcloud.sh
```

### Step 2: Create Cloud SQL Instance
```bash
# Create the PostgreSQL instance
./scripts/create-cloud-sql-instance.sh
```

## 📊 What Gets Created

### Cloud SQL Instance
- **Instance ID**: `loist-music-library-db`
- **Machine Type**: `db-n1-standard-1` (1 vCPU, 3.75GB RAM)
- **Storage**: 20GB SSD with auto-increase
- **Region**: `us-central1`
- **Version**: PostgreSQL 15

### Database Configuration
- **Database Name**: `music_library`
- **Application User**: `music_library_user`
- **Root User**: `postgres`
- **Performance Tuning**: Optimized for SSD storage

### Security Features
- **Authentication**: Cloud SQL Auth Proxy
- **Encryption**: SSL/TLS required
- **Backup**: Daily automated backups (7-day retention)
- **Point-in-Time Recovery**: Enabled

## 💰 Cost Estimation

### Monthly Costs (MVP Scale)
- **Cloud SQL Instance**: ~$50/month
- **Storage (20GB SSD)**: ~$5/month
- **Backups**: ~$2/month
- **Total**: ~$57/month

### Scaling Projections
- **Year 1 (10,000 tracks)**: ~$75/month
- **Year 2 (50,000 tracks)**: ~$150/month

## 🔐 Security Notes

### Files Created
- `.env.database` - Database configuration (add to .gitignore)
- `service-account-key.json` - Service account credentials (add to .gitignore)

### Important Security Actions
1. **Add to .gitignore**:
   ```bash
   echo "service-account-key.json" >> .gitignore
   echo ".env.database" >> .gitignore
   ```

2. **Set Environment Variables**:
   ```bash
   export GCP_PROJECT_ID="your-project-id"
   export GOOGLE_APPLICATION_CREDENTIALS="./service-account-key.json"
   ```

## 🧪 Testing the Setup

### Test Connection
```bash
# Load environment variables
source .env.database

# Test with Cloud SQL Proxy (if installed)
cloud_sql_proxy -instances=$DB_CONNECTION_NAME=tcp:5432 &
psql "postgresql://$DB_USER:$DB_PASSWORD@localhost:5432/$DB_NAME"
```

### Verify Instance
```bash
# Check instance status
gcloud sql instances describe loist-music-library-db

# List databases
gcloud sql databases list --instance=loist-music-library-db

# List users
gcloud sql users list --instance=loist-music-library-db
```

## 📚 Documentation Created

After running the script, you'll find:

- `docs/task-2.2-deployment-summary.md` - Complete deployment details
- `docs/task-2.2-github-strategy.md` - GitHub workflow strategy
- `docs/task-2.2-implementation-checklist.md` - Detailed implementation steps
- `docs/research-postgresql-cloud-sql-options.md` - Research findings

## 🚨 Troubleshooting

### Common Issues

#### 1. Authentication Error
```bash
# Re-authenticate with Google Cloud
gcloud auth login
gcloud auth application-default login
```

#### 2. Permission Denied
```bash
# Check your project permissions
gcloud projects get-iam-policy your-project-id
```

#### 3. Instance Already Exists
```bash
# Delete existing instance (if needed)
gcloud sql instances delete loist-music-library-db
```

#### 4. API Not Enabled
```bash
# Enable required APIs
gcloud services enable sqladmin.googleapis.com
gcloud services enable storage.googleapis.com
```

### Getting Help

1. **Check Logs**: The scripts provide detailed logging
2. **Google Cloud Console**: Monitor in the Cloud SQL section
3. **Documentation**: Review the created documentation files
4. **Support**: Check Google Cloud support documentation

## ✅ Success Criteria

After successful execution, you should have:

- [ ] Cloud SQL PostgreSQL instance running
- [ ] Database `music_library` created
- [ ] Application user `music_library_user` created
- [ ] Performance parameters configured
- [ ] Backup strategy implemented
- [ ] Security settings applied
- [ ] Documentation created
- [ ] Environment variables configured

## 🔄 Next Steps

1. **Run Database Migrations**: Apply the schema from Task 2.1
2. **Test Application Connection**: Verify your app can connect
3. **Set Up Monitoring**: Configure Cloud Monitoring alerts
4. **Review Costs**: Monitor usage in Google Cloud Console
5. **Plan Scaling**: Prepare for growth beyond MVP

## 📞 Support

If you encounter issues:

1. Check the script logs for detailed error messages
2. Review the Google Cloud Console for instance status
3. Verify your project permissions and billing
4. Consult the comprehensive documentation created

---

**Ready to start? Run `./scripts/execute-task-2.2.sh` from the project root!**
