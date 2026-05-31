#!/bin/bash
# Inicjalizacja LocalStack - tworzy bucket S3 używany przez aplikację

set -e

echo "[LocalStack init] Tworzenie bucketu fund-tracker-data..."

awslocal s3 mb s3://fund-tracker-data --region eu-central-1 || echo "Bucket już istnieje"

awslocal s3api put-bucket-cors \
  --bucket fund-tracker-data \
  --cors-configuration '{
    "CORSRules": [{
      "AllowedHeaders": ["*"],
      "AllowedMethods": ["GET","PUT","POST","DELETE","HEAD"],
      "AllowedOrigins": ["*"],
      "ExposeHeaders": ["ETag"]
    }]
  }'

echo "[LocalStack init] Gotowe. Bucket: fund-tracker-data"
