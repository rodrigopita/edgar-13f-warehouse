#!/usr/bin/env bash
# append_only_probe.sh: the landing bucket is append-only for the pipeline.
# As edgar-pipeline (IAM user edgar-13f-warehouse-airflow), put one throwaway
# object under probes/, which no bucket notification watches, then try to
# delete it two ways. Expected: the put succeeds, both deletes fail with
# AccessDenied, and the admin listing still shows the object. The object
# stays as the evidence; only the account owner could remove it.
set -u
B=edgar-13f-warehouse-landing-rp
K="probes/append-only/$(date -u +%Y%m%dT%H%M%SZ).txt"

echo "== whoami"
AWS_PROFILE=edgar-pipeline aws sts get-caller-identity --query Arn --output text

echo "== put s3://$B/$K"
echo "append-only probe $(date -u +%FT%TZ)" | AWS_PROFILE=edgar-pipeline aws s3 cp - "s3://$B/$K"

echo "== aws s3 rm (expected: AccessDenied)"
AWS_PROFILE=edgar-pipeline aws s3 rm "s3://$B/$K"

echo "== aws s3api delete-object (expected: AccessDenied)"
AWS_PROFILE=edgar-pipeline aws s3api delete-object --bucket "$B" --key "$K"

echo "== versions of the key, as admin (expected: one version, no delete marker)"
AWS_PROFILE=admin aws s3api list-object-versions --bucket "$B" --prefix "$K" \
    --query '{versions: Versions[].[Key, VersionId, IsLatest], delete_markers: DeleteMarkers}'
