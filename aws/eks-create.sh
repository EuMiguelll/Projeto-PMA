#!/usr/bin/env bash
# Cria a infraestrutura na AWS seguindo o roteiro do enunciado (página EKS):
#   1. VPC via CloudFormation (template amazon-eks-vpc-private-subnets.yaml)
#   2. role do cluster  3. cluster EKS  4. role do node group  5. node group  6. kubeconfig
# ⚠️ GERA CUSTOS (~US$ 0,30/h com 2 x t3.medium). Ao terminar: ./aws/eks-teardown.sh
# AWS Academy (sem permissão de IAM): CLUSTER_ROLE_ARN=... NODE_ROLE_ARN=... (LabRole)
set -euo pipefail
cd "$(dirname "$0")"
export AWS_REGION=${AWS_REGION:-us-east-2}
CLUSTER=${CLUSTER:-eks-store}
NODE_TYPE=${NODE_TYPE:-t3.medium}
NODES=${NODES:-2}
STACK=$CLUSTER-vpc

aws sts get-caller-identity --query Arn --output text

echo "==> 1/6 VPC: 2 subnets públicas (load balancer) + 2 privadas (pods)"
aws cloudformation deploy --stack-name "$STACK" --template-file amazon-eks-vpc-private-subnets.yaml
out() { aws cloudformation describe-stacks --stack-name "$STACK" --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue" --output text; }
SUBNETS=$(out SubnetIds); SG=$(out SecurityGroups); VPC=$(out VpcId)
PRIVATE=$(aws ec2 describe-subnets --filters "Name=vpc-id,Values=$VPC" "Name=tag:kubernetes.io/role/internal-elb,Values=1" \
  --query 'Subnets[].SubnetId' --output text)

role() { # nome serviço políticas... -> imprime o ARN
  local name=$1 svc=$2; shift 2
  aws iam get-role --role-name "$name" >/dev/null 2>&1 || aws iam create-role --role-name "$name" \
    --assume-role-policy-document "{\"Version\":\"2012-10-17\",\"Statement\":[{\"Effect\":\"Allow\",\"Principal\":{\"Service\":\"$svc\"},\"Action\":\"sts:AssumeRole\"}]}" >/dev/null
  for p in "$@"; do aws iam attach-role-policy --role-name "$name" --policy-arn "arn:aws:iam::aws:policy/$p"; done
  aws iam get-role --role-name "$name" --query Role.Arn --output text
}

echo "==> 2/6 Role do cluster (AmazonEKSClusterPolicy)"
CLUSTER_ROLE=${CLUSTER_ROLE_ARN:-$(role eksClusterRole eks.amazonaws.com AmazonEKSClusterPolicy)}

echo "==> 3/6 Cluster $CLUSTER (~10 min)"
aws eks describe-cluster --name "$CLUSTER" >/dev/null 2>&1 || aws eks create-cluster --name "$CLUSTER" \
  --role-arn "$CLUSTER_ROLE" \
  --resources-vpc-config "subnetIds=$SUBNETS,securityGroupIds=$SG,endpointPublicAccess=true" \
  --access-config authenticationMode=API_AND_CONFIG_MAP >/dev/null
aws eks wait cluster-active --name "$CLUSTER"

echo "==> 4/6 Role do node group (CNI, WorkerNode, ECR read-only)"
NODE_ROLE=${NODE_ROLE_ARN:-$(role eksNodeRole ec2.amazonaws.com AmazonEKS_CNI_Policy AmazonEKSWorkerNodePolicy AmazonEC2ContainerRegistryReadOnly)}

echo "==> 5/6 Node group: $NODES x $NODE_TYPE só nas subnets privadas (~5 min)"
aws eks describe-nodegroup --cluster-name "$CLUSTER" --nodegroup-name "$CLUSTER-nodes" >/dev/null 2>&1 || \
  aws eks create-nodegroup --cluster-name "$CLUSTER" --nodegroup-name "$CLUSTER-nodes" \
    --node-role "$NODE_ROLE" --subnets $PRIVATE --instance-types "$NODE_TYPE" --disk-size 20 \
    --scaling-config "minSize=$NODES,maxSize=$((NODES + 1)),desiredSize=$NODES" >/dev/null
aws eks wait nodegroup-active --cluster-name "$CLUSTER" --nodegroup-name "$CLUSTER-nodes"

echo "==> 6/6 kubeconfig + metrics-server (o HPA precisa das métricas de CPU)"
aws eks update-kubeconfig --name "$CLUSTER"
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
kubectl get nodes -o wide
echo "Pronto. Próximo passo: DOCKERHUB_USERNAME=<usuario> ./k8s/deploy.sh"
