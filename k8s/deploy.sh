#!/usr/bin/env bash
# Build, push, and deploy all OMS services to EKS.
#
# Usage:
#   export AWS_ACCOUNT_ID=123456789012
#   export AWS_REGION=us-east-1
#   export IMAGE_TAG=v1.0.0          # defaults to git SHA
#   export CLUSTER_NAME=oms-eks
#   ./k8s/deploy.sh [--infra] [--app] [--all]
#
# Flags (default: --app only):
#   --infra   deploy in-cluster Kafka/Postgres/Redis
#   --app     build, push, and deploy application services
#   --all     deploy infra + app

set -euo pipefail

AWS_ACCOUNT_ID=${AWS_ACCOUNT_ID:?Set AWS_ACCOUNT_ID}
AWS_REGION=${AWS_REGION:?Set AWS_REGION}
CLUSTER_NAME=${CLUSTER_NAME:?Set CLUSTER_NAME}
IMAGE_TAG=${IMAGE_TAG:-$(git rev-parse --short HEAD)}
ECR_REGISTRY="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"

DEPLOY_INFRA=false
DEPLOY_APP=true

for arg in "$@"; do
  case $arg in
    --infra) DEPLOY_INFRA=true; DEPLOY_APP=false ;;
    --app)   DEPLOY_APP=true ;;
    --all)   DEPLOY_INFRA=true; DEPLOY_APP=true ;;
  esac
done

SERVICES=(fix-gateway order-service matching-engine risk-engine market-data-service ui)

# ── ECR login ──────────────────────────────────────────────────────────────
ecr_login() {
  echo "→ Logging in to ECR..."
  aws ecr get-login-password --region "$AWS_REGION" \
    | docker login --username AWS --password-stdin "$ECR_REGISTRY"
}

# ── Ensure ECR repos exist ─────────────────────────────────────────────────
ensure_repos() {
  for svc in "${SERVICES[@]}"; do
    aws ecr describe-repositories --region "$AWS_REGION" \
      --repository-names "oms/$svc" > /dev/null 2>&1 || \
    aws ecr create-repository --region "$AWS_REGION" \
      --repository-name "oms/$svc" --image-scanning-configuration scanOnPush=true
    echo "  ECR repo: oms/$svc"
  done
}

# ── Build & push images ────────────────────────────────────────────────────
build_and_push() {
  for svc in "${SERVICES[@]}"; do
    local image="${ECR_REGISTRY}/oms/${svc}:${IMAGE_TAG}"
    local dockerfile="services/${svc}/Dockerfile"
    echo "→ Building $svc → $image"

    # FIX services require x86 image for quickfix compatibility
    if [[ "$svc" == "fix-gateway" || "$svc" == "market-data-service" ]]; then
      docker buildx build --platform linux/amd64 -t "$image" -f "$dockerfile" . --push
    else
      docker buildx build --platform linux/arm64,linux/amd64 -t "$image" -f "$dockerfile" . --push
    fi
  done
}

# ── Patch image tags in manifests and apply ────────────────────────────────
deploy_app() {
  echo "→ Updating kubeconfig for cluster $CLUSTER_NAME..."
  aws eks update-kubeconfig --region "$AWS_REGION" --name "$CLUSTER_NAME"

  echo "→ Substituting image tags..."
  local tmp_dir
  tmp_dir=$(mktemp -d)
  cp -r k8s/. "$tmp_dir/"

  for svc in "${SERVICES[@]}"; do
    local image="${ECR_REGISTRY}/oms/${svc}:${IMAGE_TAG}"
    sed -i.bak \
      "s|ACCOUNT_ID.dkr.ecr.REGION.amazonaws.com/oms/${svc}:TAG|${image}|g" \
      "$tmp_dir/${svc}/deployment.yaml"
  done

  echo "→ Applying namespace and config..."
  kubectl apply -f "$tmp_dir/namespace.yaml"
  kubectl apply -f "$tmp_dir/configmap.yaml"
  # Apply secret only if it doesn't exist (avoid overwriting production values)
  kubectl apply -f "$tmp_dir/secret.yaml" --dry-run=client -o yaml \
    | kubectl apply --server-side --force-conflicts -f - || true

  echo "→ Applying application manifests..."
  for svc in "${SERVICES[@]}"; do
    kubectl apply -f "$tmp_dir/${svc}/"
  done
  kubectl apply -f "$tmp_dir/ingress.yaml"

  rm -rf "$tmp_dir"
  echo "→ Waiting for rollout..."
  for svc in "${SERVICES[@]}"; do
    kubectl rollout status deployment/"$svc" -n oms --timeout=300s || true
  done
}

deploy_infra() {
  echo "→ Applying in-cluster infra (Kafka, Postgres, Redis)..."
  kubectl apply -f k8s/namespace.yaml
  kubectl apply -f k8s/infra/
  echo "→ Waiting for Kafka broker to be ready..."
  kubectl wait --for=condition=ready pod -l app=kafka-broker -n oms --timeout=180s
  kubectl wait --for=condition=complete job/kafka-init -n oms --timeout=120s
}

# ── Main ───────────────────────────────────────────────────────────────────
ecr_login
ensure_repos

if $DEPLOY_INFRA; then
  deploy_infra
fi

if $DEPLOY_APP; then
  build_and_push
  deploy_app
fi

echo "✓ Deploy complete. Image tag: $IMAGE_TAG"
