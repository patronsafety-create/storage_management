#!/bin/bash
# ==============================================================================
# NexusPour ERP - Automated Database Backup Script
# Developer & Intellectual Property: Omid Pourmahmoud
# ==============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BACKUP_DIR="$PROJECT_DIR/backups"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="$BACKUP_DIR/storage_erp_backup_${TIMESTAMP}.sql.gz"
LOG_FILE="$BACKUP_DIR/backup.log"

mkdir -p "$BACKUP_DIR"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] شروع تهیه نسخه پشتیبان از پایگاه‌داده PostgreSQL..." >> "$LOG_FILE"

# اجرای مستقیم pg_dump از کانتینر داکر
if docker exec storage_management-db-1 pg_dump -U erp_user storage_erp | gzip > "$BACKUP_FILE"; then
    FILE_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ✅ نسخه پشتیبان با موفقیت ذخیره شد: $BACKUP_FILE (حجم: $FILE_SIZE)" >> "$LOG_FILE"
    echo "Backup successful: $BACKUP_FILE ($FILE_SIZE)"
else
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ❌ خطا در تهیه نسخه پشتیبان!" >> "$LOG_FILE"
    echo "Backup failed!" >&2
    exit 1
fi

# پاکسازی پشتیبان‌های قدیمی‌تر از ۱۴ روز
find "$BACKUP_DIR" -name "storage_erp_backup_*.sql.gz" -mtime +14 -delete
echo "[$(date '+%Y-%m-%d %H:%M:%S')] پاکسازی فایل‌های قدیمی‌تر از ۱۴ روز انجام شد." >> "$LOG_FILE"
