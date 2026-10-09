#!/usr/bin/env sh
set -eu

: "${DEPLOY_COMMIT:?DEPLOY_COMMIT is required}"
: "${BOREAL_ECR_IMAGE:?BOREAL_ECR_IMAGE is required}"
: "${AWS_REGION:?AWS_REGION is required}"

project_dir="${BOREAL_PROJECT_DIR:-/opt/boreal-marche}"
cd "$project_dir"

git fetch --prune origin
git checkout --detach "$DEPLOY_COMMIT"

registry="${BOREAL_ECR_IMAGE%%/*}"
aws ecr get-login-password --region "$AWS_REGION" \
  | docker login --username AWS --password-stdin "$registry"

export BOREAL_IMAGE_TAG="$DEPLOY_COMMIT"
docker compose \
  --env-file deploy/aws/.env \
  -f deploy/aws/compose.yaml \
  -f deploy/aws/compose.deploy.yaml \
  pull api
docker compose \
  --env-file deploy/aws/.env \
  -f deploy/aws/compose.yaml \
  -f deploy/aws/compose.deploy.yaml \
  up -d --no-build api

sh deploy/aws/smoke_test.sh
docker image inspect "${BOREAL_ECR_IMAGE}:${BOREAL_IMAGE_TAG}" \
  --format 'image={{index .RepoDigests 0}} size={{.Size}}'
