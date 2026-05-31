#!/usr/bin/env bash
# deploy.sh — Build, push Docker images to ECR and force-update ECS services.
# Usage:
#   ./deploy.sh                  # deploy both services
#   ./deploy.sh backend          # backend only
#   ./deploy.sh frontend         # frontend only
#   ./deploy.sh --skip-build     # push existing local images (skip docker build)
#
# Prerequisites: aws-cli v2, docker, terraform (optional — only for outputs)
# Region and project are read from terraform.tfvars or environment variables.

set -euo pipefail

# ── Config ────────────────────────────────────────────────────────────────────

AWS_REGION="${AWS_REGION:-eu-west-1}"
ENVIRONMENT="${ENVIRONMENT:-prod}"
PROJECT="${PROJECT:-fund-tracker}"
PREFIX="${PROJECT}-${ENVIRONMENT}"

# Resolve project root (two levels up from infrastructure/terraform/)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

TARGET="${1:-all}"
SKIP_BUILD=false
if [[ "${TARGET}" == "--skip-build" ]]; then
  SKIP_BUILD=true
  TARGET="all"
fi

ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
ECR_BASE="${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
BACKEND_REPO="${ECR_BASE}/${PREFIX}/backend"
FRONTEND_REPO="${ECR_BASE}/${PREFIX}/frontend"

IMAGE_TAG="${IMAGE_TAG:-$(git -C "${PROJECT_ROOT}" rev-parse --short HEAD 2>/dev/null || echo latest)}"

# ── ECR login ────────────────────────────────────────────────────────────────

echo "→ Logging in to ECR (${ECR_BASE})…"
aws ecr get-login-password --region "${AWS_REGION}" \
  | docker login --username AWS --password-stdin "${ECR_BASE}"

# ── Build & push backend ──────────────────────────────────────────────────────

deploy_backend() {
  if [[ "${SKIP_BUILD}" == false ]]; then
    echo "→ Building backend image…"
    docker build \
      --platform linux/amd64 \
      -t "${BACKEND_REPO}:${IMAGE_TAG}" \
      -t "${BACKEND_REPO}:latest" \
      "${PROJECT_ROOT}/backend"
  fi

  echo "→ Pushing backend image (${IMAGE_TAG})…"
  docker push "${BACKEND_REPO}:${IMAGE_TAG}"
  docker push "${BACKEND_REPO}:latest"

  echo "→ Forcing ECS backend service update…"
  aws ecs update-service \
    --region "${AWS_REGION}" \
    --cluster "${PREFIX}-cluster" \
    --service "${PREFIX}-backend" \
    --force-new-deployment \
    --output text \
    --query "service.serviceName"
}

# ── Build & push frontend ─────────────────────────────────────────────────────
# NEXT_PUBLIC_API_URL is baked at build time. Defaults to the ALB URL which
# can be retrieved from Terraform outputs or overridden via env var.

deploy_frontend() {
  ALB_DNS="${API_URL:-}"
  if [[ -z "${ALB_DNS}" ]]; then
    echo "→ Reading NEXT_PUBLIC_API_URL from Terraform outputs…"
    ALB_DNS="$(
      cd "${SCRIPT_DIR}" && \
      terraform output -raw alb_dns_name 2>/dev/null || true
    )"
  fi
  NEXT_PUBLIC_API_URL="${ALB_DNS:+http://${ALB_DNS}}"

  if [[ "${SKIP_BUILD}" == false ]]; then
    echo "→ Building frontend image (NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL:-<not set>})…"
    docker build \
      --platform linux/amd64 \
      ${NEXT_PUBLIC_API_URL:+--build-arg NEXT_PUBLIC_API_URL="${NEXT_PUBLIC_API_URL}"} \
      -t "${FRONTEND_REPO}:${IMAGE_TAG}" \
      -t "${FRONTEND_REPO}:latest" \
      "${PROJECT_ROOT}/frontend"
  fi

  echo "→ Pushing frontend image (${IMAGE_TAG})…"
  docker push "${FRONTEND_REPO}:${IMAGE_TAG}"
  docker push "${FRONTEND_REPO}:latest"

  echo "→ Forcing ECS frontend service update…"
  aws ecs update-service \
    --region "${AWS_REGION}" \
    --cluster "${PREFIX}-cluster" \
    --service "${PREFIX}-frontend" \
    --force-new-deployment \
    --output text \
    --query "service.serviceName"
}

# ── Main ──────────────────────────────────────────────────────────────────────

case "${TARGET}" in
  backend)
    deploy_backend
    ;;
  frontend)
    deploy_frontend
    ;;
  all)
    deploy_backend
    deploy_frontend
    ;;
  *)
    echo "Unknown target: ${TARGET}. Use: backend | frontend | all | --skip-build"
    exit 1
    ;;
esac

echo ""
echo "✓ Done. Tag: ${IMAGE_TAG}"
echo "  App:  http://$(cd "${SCRIPT_DIR}" && terraform output -raw alb_dns_name 2>/dev/null || echo '<run terraform output alb_dns_name>')"
