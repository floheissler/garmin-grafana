#!/bin/bash
# InfluxDB Backup Script for Garmin-Grafana
# Creates portable backups of the GarminStats database

set -e

BACKUP_ROOT="./influxdb_backups"
TIMESTAMP=$(date +%F_%H-%M)
BACKUP_DIR="$BACKUP_ROOT/$TIMESTAMP"

echo "Creating backup directory: $BACKUP_DIR"
mkdir -p "$BACKUP_DIR"

echo "Backing up GarminStats database..."
docker exec influxdb influxd backup -portable -db GarminStats /tmp/influxdb_backup

echo "Copying backup to host..."
docker cp influxdb:/tmp/influxdb_backup/. "$BACKUP_DIR/"

echo "Cleaning up container temp files..."
docker exec influxdb rm -r /tmp/influxdb_backup

# Show backup size
BACKUP_SIZE=$(du -sh "$BACKUP_DIR" | cut -f1)
echo ""
echo "Backup complete!"
echo "  Location: $BACKUP_DIR"
echo "  Size: $BACKUP_SIZE"

# Remove backups older than 30 days
find "$BACKUP_ROOT" -mindepth 1 -maxdepth 1 -type d -mtime +30 -exec rm -rf {} \; 2>/dev/null || true
