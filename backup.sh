#!/bin/bash
# Daily backup of the SQLite database to S3. Needs an IAM role with s3:PutObject on the bucket.
# Usage: BUCKET=my-bucket ./deploy/backup.sh      (see docs/AWS_DEPLOYMENT.md, step 9)
set -euo pipefail
: "${BUCKET:?Set BUCKET=your-s3-bucket}"
STAMP=$(date +%F)
docker compose exec -T web python - <<'PY'
import sqlite3
src = sqlite3.connect("/data/prepledger.db")
dst = sqlite3.connect("/data/backup.db")
src.backup(dst); dst.close(); src.close()
PY
docker compose cp web:/data/backup.db "/tmp/prepledger-$STAMP.db"
aws s3 cp "/tmp/prepledger-$STAMP.db" "s3://$BUCKET/prepledger/$STAMP.db" --sse AES256
rm -f "/tmp/prepledger-$STAMP.db"
echo "Backup uploaded: s3://$BUCKET/prepledger/$STAMP.db"
