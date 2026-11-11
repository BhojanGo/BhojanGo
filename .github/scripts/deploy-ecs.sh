#!/usr/bin/env bash
# Deploy the three backend services to one environment on ECS Fargate.
#
#   .github/scripts/deploy-ecs.sh <staging|prod> <image-tag>
#
# Expects AWS credentials in the environment (GitHub OIDC role) and the
# images already pushed as <registry>/bhojango-<env>/<service>:<image-tag>.
# Reads the cluster, subnets and security group from the SSM parameters that
# Terraform writes (/bhojango-<env>/deploy/*), so no Terraform state is needed.
#
# Steps: register a new task-definition revision per service with the new
# image -> run `alembic upgrade head` once as a one-off core-api task and fail
# the deploy if it fails -> point each service at its new revision -> wait
# until all three are stable (the ECS circuit breaker rolls back failures).
set -euo pipefail

ENV="${1:?usage: deploy-ecs.sh <staging|prod> <image-tag>}"
TAG="${2:?usage: deploy-ecs.sh <staging|prod> <image-tag>}"
NAME="bhojango-${ENV}"
SERVICES=(core-api realtime worker)

param() { aws ssm get-parameter --name "/${NAME}/deploy/$1" --query Parameter.Value --output text; }

CLUSTER="$(param cluster)"
REGISTRY="$(param ecr_registry)"
SUBNETS="$(param private_subnet_ids)"
SECURITY_GROUP="$(param ecs_security_group)"

declare -A TASK_DEF
for svc in "${SERVICES[@]}"; do
  image="${REGISTRY}/${NAME}/${svc}:${TAG}"
  echo "::group::Register ${svc} -> ${image}"
  current="$(aws ecs describe-task-definition --task-definition "${NAME}-${svc}" --query taskDefinition)"
  new="$(jq --arg img "$image" '
      .containerDefinitions[0].image = $img
      | del(.taskDefinitionArn, .revision, .status, .requiresAttributes,
            .compatibilities, .registeredAt, .registeredBy)' <<<"$current")"
  TASK_DEF[$svc]="$(aws ecs register-task-definition --cli-input-json "$new" \
      --query taskDefinition.taskDefinitionArn --output text)"
  echo "${TASK_DEF[$svc]}"
  echo "::endgroup::"
done

echo "::group::Migrations (alembic upgrade head)"
network="awsvpcConfiguration={subnets=[${SUBNETS}],securityGroups=[${SECURITY_GROUP}],assignPublicIp=DISABLED}"
overrides='{"containerOverrides":[{"name":"core-api","command":["alembic","upgrade","head"]}]}'
task_arn="$(aws ecs run-task --cluster "$CLUSTER" --task-definition "${TASK_DEF[core-api]}" \
    --launch-type FARGATE --network-configuration "$network" --overrides "$overrides" \
    --started-by "github-${GITHUB_RUN_ID:-manual}" --query 'tasks[0].taskArn' --output text)"
echo "migration task: ${task_arn}"
aws ecs wait tasks-stopped --cluster "$CLUSTER" --tasks "$task_arn"
exit_code="$(aws ecs describe-tasks --cluster "$CLUSTER" --tasks "$task_arn" \
    --query 'tasks[0].containers[0].exitCode' --output text)"
reason="$(aws ecs describe-tasks --cluster "$CLUSTER" --tasks "$task_arn" \
    --query 'tasks[0].stoppedReason' --output text)"
echo "exit code: ${exit_code} (${reason})"
echo "logs: CloudWatch log group /${NAME}/core-api"
echo "::endgroup::"
if [ "$exit_code" != "0" ]; then
  echo "::error::Migrations failed (exit ${exit_code}); services were not updated."
  exit 1
fi

for svc in "${SERVICES[@]}"; do
  echo "Updating ${NAME}-${svc}"
  aws ecs update-service --cluster "$CLUSTER" --service "${NAME}-${svc}" \
      --task-definition "${TASK_DEF[$svc]}" --query 'service.deployments[0].id' --output text
done

echo "Waiting for the services to become stable..."
aws ecs wait services-stable --cluster "$CLUSTER" \
    --services "${SERVICES[@]/#/${NAME}-}"

echo "Deployed ${TAG} to ${ENV}: http://$(param alb_dns_name)"
