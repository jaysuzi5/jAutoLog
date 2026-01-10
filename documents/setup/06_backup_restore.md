# Database Backup and Restore Procedures

## Overview

jAutoLog uses a multi-tiered backup strategy:

1. **Local Backups**: Every 6 hours to NFS storage (7 day retention)
2. **Daily Cloud Backups**: Daily at 2 AM to S3 (30 day retention)
3. **Monthly Cloud Backups**: 1st of each month at 3 AM to S3 (long-term archival)

All backups are created using PostgreSQL's `pg_dump` in custom format with maximum compression.

## Backup Locations

### Local Backups (NFS)
- **Path**: `/backups/` on the backup PVC
- **Format**: `jautolog_YYYYMMDD_HHMMSS.dump`
- **Retention**: 7 days

### S3 Daily Backups
- **Path**: `s3://jay-curtis-backup/jautolog/backups/daily/YYYY/MM/DD/`
- **Format**: `jautolog_YYYYMMDD_HHMMSS.dump`
- **Retention**: 30 days (configurable via S3 lifecycle policies)

### S3 Monthly Backups
- **Path**: `s3://jay-curtis-backup/jautolog/backups/monthly/YYYY/MM/`
- **Format**: `jautolog_YYYYMMDD_HHMMSS.dump`
- **Retention**: Indefinite (long-term archival)

---

## Restore Procedures

### Prerequisites

Before restoring:

1. **⚠️ STOP THE APPLICATION** to prevent data corruption:
   ```bash
   kubectl scale deployment jautolog --replicas=0 -n jautolog
   ```

2. **Backup current database** (if it contains any recent data you might need):
   ```bash
   kubectl create job --from=cronjob/jautolog-postgres-backup-local manual-backup-before-restore -n jautolog
   ```

---

## Option 1: Restore from S3 Backup (Recommended for older backups)

### Step 1: List Available Backups

**List recent daily backups:**
```bash
kubectl run aws-cli --rm -i --restart=Never --image=amazon/aws-cli:latest -n jautolog \
  --env="AWS_ACCESS_KEY_ID=$(kubectl get secret jautolog -n jautolog -o jsonpath='{.data.AWS_ACCESS_KEY_ID}' | base64 -d)" \
  --env="AWS_SECRET_ACCESS_KEY=$(kubectl get secret jautolog -n jautolog -o jsonpath='{.data.AWS_SECRET_ACCESS_KEY}' | base64 -d)" \
  --env="AWS_DEFAULT_REGION=us-east-1" \
  -- aws s3 ls s3://jay-curtis-backup/jautolog/backups/daily/ --recursive --human-readable | tail -30
```

**List monthly backups:**
```bash
kubectl run aws-cli --rm -i --restart=Never --image=amazon/aws-cli:latest -n jautolog \
  --env="AWS_ACCESS_KEY_ID=$(kubectl get secret jautolog -n jautolog -o jsonpath='{.data.AWS_ACCESS_KEY_ID}' | base64 -d)" \
  --env="AWS_SECRET_ACCESS_KEY=$(kubectl get secret jautolog -n jautolog -o jsonpath='{.data.AWS_SECRET_ACCESS_KEY}' | base64 -d)" \
  --env="AWS_DEFAULT_REGION=us-east-1" \
  -- aws s3 ls s3://jay-curtis-backup/jautolog/backups/monthly/ --recursive --human-readable
```

### Step 2: Edit the Restore Job

Open `k8s/restore-job.yaml` and update the `S3_BACKUP_PATH` environment variable with the backup you want to restore:

```yaml
- name: S3_BACKUP_PATH
  value: "jautolog/backups/daily/2026/01/10/jautolog_20260110_120000.dump"
```

### Step 3: Run the Restore Job

```bash
kubectl apply -f k8s/restore-job.yaml
```

### Step 4: Monitor the Restore

```bash
# Watch the job status
kubectl get jobs -n jautolog -w

# View restore logs (streaming)
kubectl logs -f job/postgres-restore -n jautolog
```

The restore will show progress and any warnings. Some warnings like "role does not exist" are normal and can be ignored.

### Step 5: Verify and Restart Application

```bash
# Check if restore completed successfully
kubectl get job postgres-restore -n jautolog

# If successful, restart the application
kubectl scale deployment jautolog --replicas=1 -n jautolog

# Clean up the restore job
kubectl delete job postgres-restore -n jautolog
```

---

## Option 2: Restore from Local NFS Backup (Faster for recent backups)

### Step 1: List Available Local Backups

```bash
kubectl run postgres-client --rm -i --restart=Never --image=postgres:17-alpine -n jautolog \
  --overrides='
{
  "spec": {
    "containers": [{
      "name": "client",
      "image": "postgres:17-alpine",
      "command": ["ls", "-lh", "/backups/"],
      "volumeMounts": [{
        "name": "backup-storage",
        "mountPath": "/backups",
        "readOnly": true
      }]
    }],
    "volumes": [{
      "name": "backup-storage",
      "persistentVolumeClaim": {
        "claimName": "jautolog-postgres-backup-pvc"
      }
    }]
  }
}'
```

### Step 2: Restore from Local Backup

Replace `BACKUP_FILENAME` with the actual filename from Step 1:

```bash
kubectl run postgres-restore --rm -i --restart=Never --image=postgres:17-alpine -n jautolog \
  --overrides='
{
  "spec": {
    "containers": [{
      "name": "restore",
      "image": "postgres:17-alpine",
      "command": ["/bin/sh", "-c"],
      "args": ["PGPASSWORD=\"$POSTGRES_PASSWORD\" pg_restore -h postgresql-rw.postgresql.svc.cluster.local -U \"$POSTGRES_USER\" -d \"$POSTGRES_DB\" --clean --if-exists --verbose /backups/BACKUP_FILENAME"],
      "env": [
        {
          "name": "POSTGRES_DB",
          "valueFrom": {
            "configMapKeyRef": {
              "name": "jautolog-config",
              "key": "DATABASE_NAME"
            }
          }
        },
        {
          "name": "POSTGRES_USER",
          "valueFrom": {
            "secretKeyRef": {
              "name": "jautolog",
              "key": "username"
            }
          }
        },
        {
          "name": "POSTGRES_PASSWORD",
          "valueFrom": {
            "secretKeyRef": {
              "name": "jautolog",
              "key": "password"
            }
          }
        }
      ],
      "volumeMounts": [{
        "name": "backup-storage",
        "mountPath": "/backups",
        "readOnly": true
      }]
    }],
    "volumes": [{
      "name": "backup-storage",
      "persistentVolumeClaim": {
        "claimName": "jautolog-postgres-backup-pvc"
      }
    }]
  }
}'
```

---

## Common pg_restore Options

- `--clean`: Drop database objects before recreating them
- `--if-exists`: Use IF EXISTS when dropping objects (prevents errors)
- `--no-owner`: Skip restoration of object ownership
- `--no-acl`: Skip restoration of access privileges
- `--verbose`: Show detailed progress
- `--data-only`: Restore only data, not schema (for schema-only changes)
- `--schema-only`: Restore only schema, not data (for testing schema changes)

---

## Troubleshooting

### Error: "database is being accessed by other users"

The application is still running. Stop it first:
```bash
kubectl scale deployment jautolog --replicas=0 -n jautolog
```

### Error: "role does not exist"

This is normal when using `--no-owner`. The restore script skips setting ownership.

### Partial Restore (specific tables only)

Use `-t` to restore specific tables:
```bash
-t table_name1 -t table_name2
```

### Restore to a Different Database Name

Use `-d` with a different database name:
```bash
PGPASSWORD="$POSTGRES_PASSWORD" pg_restore \
  -h postgresql-rw.postgresql.svc.cluster.local \
  -U postgres \
  -d jautolog_test \  # Different database
  --clean --if-exists \
  /backups/backup_file.dump
```

---

## Testing Restore Procedure

It's recommended to periodically test your restore procedure:

1. Create a test namespace:
   ```bash
   kubectl create namespace jautolog-test
   ```

2. Deploy a test PostgreSQL instance
3. Restore a backup to the test database
4. Verify data integrity
5. Clean up the test environment

---

## Automated Restore Testing (Future Enhancement)

Consider creating a monthly cronjob that:
1. Spins up a temporary PostgreSQL instance
2. Restores the latest monthly backup
3. Runs basic data validation queries
4. Sends notification of success/failure
5. Cleans up resources

This ensures your backups are actually restorable when you need them.

---

## Emergency Contact Information

In case of critical data loss:

1. **DO NOT PANIC** - All backups are retained
2. Check local backups first (fastest restore)
3. Check S3 daily backups (last 30 days)
4. Check S3 monthly backups (long-term)
5. Document what happened for post-mortem analysis

---

## Backup Verification

Periodically verify backups are being created:

```bash
# Check local backups
kubectl exec deployment/jautolog -n jautolog -- ls -lh /backups/ 2>/dev/null || echo "No local backups accessible from app pod"

# Check S3 backups (requires AWS CLI configured)
aws s3 ls s3://jay-curtis-backup/jautolog/backups/daily/ --recursive | tail -5
aws s3 ls s3://jay-curtis-backup/jautolog/backups/monthly/ --recursive
```

# Check cronjob status
```bash
kubectl get cronjobs -n jautolog
kubectl get jobs -n jautolog --sort-by=.status.startTime | tail -10
```
