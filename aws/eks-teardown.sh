#!/usr/bin/env bash
# Remove TUDO o que eks-create.sh / rds-create.sh / push-images.sh criaram (para de cobrar).
# A ordem importa: os ELBs criados pelo Kubernetes precisam sumir antes da VPC.
set -uo pipefail
export AWS_REGION=${AWS_REGION:-us-east-2}
CLUSTER=${CLUSTER:-eks-store}
DB=$CLUSTER-db

echo "==> 1/6 Services LoadBalancer e Ingress (libera os ELBs)"
# garante que o kubectl aponta para este cluster (e não para um kind/minikube local)
aws eks update-kubeconfig --name "$CLUSTER" >/dev/null && kubectl delete ingress --all --ignore-not-found --timeout=180s
kubectl delete svc gateway --ignore-not-found --timeout=180s

echo "==> 2/6 RDS (se existir)"
if aws rds describe-db-instances --db-instance-identifier "$DB" >/dev/null 2>&1; then
  aws rds delete-db-instance --db-instance-identifier "$DB" --skip-final-snapshot --delete-automated-backups >/dev/null
  aws rds wait db-instance-deleted --db-instance-identifier "$DB"
fi
aws rds delete-db-subnet-group --db-subnet-group-name "$DB-subnets" 2>/dev/null
SG=$(aws ec2 describe-security-groups --filters "Name=group-name,Values=$DB-sg" --query 'SecurityGroups[0].GroupId' --output text 2>/dev/null)
if [[ -n "$SG" && "$SG" != None ]]; then # a ENI do RDS demora um pouco para ser liberada
  for _ in $(seq 10); do aws ec2 delete-security-group --group-id "$SG" && break; sleep 30; done
fi

echo "==> 3/6 Node group (~5 min)"
aws eks delete-nodegroup --cluster-name "$CLUSTER" --nodegroup-name "$CLUSTER-nodes" >/dev/null 2>&1 && \
  aws eks wait nodegroup-deleted --cluster-name "$CLUSTER" --nodegroup-name "$CLUSTER-nodes"

echo "==> 4/6 Cluster (~5 min)"
aws eks delete-cluster --name "$CLUSTER" >/dev/null 2>&1 && aws eks wait cluster-deleted --name "$CLUSTER"

echo "==> 5/6 VPC (CloudFormation: subnets, NAT gateways, elastic IPs)"
aws cloudformation delete-stack --stack-name "$CLUSTER-vpc"
aws cloudformation wait stack-delete-complete --stack-name "$CLUSTER-vpc"

echo "==> 6/6 Repositórios do ECR (imagens)"
for s in account auth exchange gateway; do
  aws ecr delete-repository --repository-name "$s-service" --force >/dev/null 2>&1
done

echo "Feito. As roles IAM (eksClusterRole, eksNodeRole) não geram custo e foram mantidas."
echo "Confira no console (região $AWS_REGION): EC2 > Load Balancers, NAT Gateways, Elastic IPs e Volumes vazios."
