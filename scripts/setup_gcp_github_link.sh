#!/usr/bin/env bash
# scripts/setup_gcp_github_link.sh
set -euo pipefail

PROJECT_ID="aerial-rarity-484202-j8"
REPO="xiancao2024/Conference-Matching-Platform"
SA_NAME="github-deployer"
POOL_NAME="github-pool"
PROVIDER_NAME="github-provider"

echo "Enabling APIs..."
gcloud services enable iam.googleapis.com iamcredentials.googleapis.com compute.googleapis.com --project="${PROJECT_ID}"

echo "Creating Service Account..."
if ! gcloud iam service-accounts describe "${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com" --project="${PROJECT_ID}" &>/dev/null; then
  gcloud iam service-accounts create "${SA_NAME}" \
    --display-name="GitHub Deployer Service Account" \
    --project="${PROJECT_ID}"
fi

echo "Setting up Workload Identity Pool..."
if ! gcloud iam workload-identity-pools describe "${POOL_NAME}" --location="global" --project="${PROJECT_ID}" &>/dev/null; then
  gcloud iam workload-identity-pools create "${POOL_NAME}" \
    --location="global" \
    --display-name="GitHub Actions Pool" \
    --project="${PROJECT_ID}"
fi

echo "Setting up Workload Identity Provider..."
if ! gcloud iam workload-identity-pools providers describe "${PROVIDER_NAME}" \
    --location="global" --workload-identity-pool="${POOL_NAME}" --project="${PROJECT_ID}" &>/dev/null; then
  gcloud iam workload-identity-pools providers create-oidc "${PROVIDER_NAME}" \
    --location="global" \
    --workload-identity-pool="${POOL_NAME}" \
    --display-name="GitHub Actions Provider" \
    --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository" \
    --issuer-uri="https://token.actions.githubusercontent.com" \
    --project="${PROJECT_ID}"
fi

PROJECT_NUMBER=$(gcloud projects describe "${PROJECT_ID}" --format='value(projectNumber)')

echo "Binding repository to Service Account..."
gcloud iam service-accounts add-iam-policy-binding "${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com" \
    --project="${PROJECT_ID}" \
    --role="roles/iam.workloadIdentityUser" \
    --member="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_NAME}/attribute.repository/${REPO}"

echo "Granting IAM roles to Service Account..."
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member="serviceAccount:${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="roles/compute.admin"
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member="serviceAccount:${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="roles/iam.serviceAccountUser"
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member="serviceAccount:${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="roles/iap.tunnelResourceAccessor"

echo "Setup Complete!"
echo ""
echo "----------------------------------------------------------------"
echo "WIF Provider ID for your GitHub Workflow:"
echo "Copy the exact resource name below into a GitHub Actions secret or repo variable named WIF_PROVIDER."
echo "This value is plain text, not a JSON credential and not a downloaded key file."
gcloud iam workload-identity-pools providers describe "${PROVIDER_NAME}" \
    --location="global" --workload-identity-pool="${POOL_NAME}" --project="${PROJECT_ID}" \
    --format='value(name)'
echo "----------------------------------------------------------------"
