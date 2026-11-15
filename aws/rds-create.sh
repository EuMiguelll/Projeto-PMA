#!/usr/bin/env bash
# OPCIONAL: Postgres gerenciado (Amazon RDS = PaaS) em vez do Postgres dentro do cluster.
# db.t4g.micro, 20 GB gp3, Single-AZ, subnets privadas, acesso só a partir dos nós do EKS.
#   DATABASE_PASSWORD='senha-forte' ./aws/rds-create.sh
set -euo pipefail
export AWS_REGION=${AWS_REGION:-us-east-2}
CLUSTER=${CLUSTER:-eks-store}
DB=$CLUSTER-db
: "${DATABASE_PASSWORD:?defina DATABASE_PASSWORD (mín. 8 caracteres)}"

VPC=$(aws cloudformation describe-stacks --stack-name "$CLUSTER-vpc" --query "Stacks[0].Outputs[?OutputKey=='VpcId'].OutputValue" --output text)
PRIVATE=$(aws ec2 describe-subnets --filters "Name=vpc-id,Values=$VPC" "Name=tag:kubernetes.io/role/internal-elb,Values=1" --query 'Subnets[].SubnetId' --output text)
NODES_SG=$(aws eks describe-cluster --name "$CLUSTER" --query cluster.resourcesVpcConfig.clusterSecurityGroupId --output text)

SG=$(aws ec2 create-security-group --group-name "$DB-sg" --description "Postgres a partir dos nos do EKS" \
  --vpc-id "$VPC" --query GroupId --output text)
aws ec2 authorize-security-group-ingress --group-id "$SG" --protocol tcp --port 5432 --source-group "$NODES_SG" >/dev/null
aws rds create-db-subnet-group --db-subnet-group-name "$DB-subnets" \
  --db-subnet-group-description "subnets privadas do $CLUSTER" --subnet-ids $PRIVATE >/dev/null
aws rds create-db-instance --db-instance-identifier "$DB" \
  --engine postgres --engine-version 17 --db-instance-class db.t4g.micro \
  --allocated-storage 20 --storage-type gp3 --no-multi-az --no-publicly-accessible \
  --master-username store --master-user-password "$DATABASE_PASSWORD" --db-name store \
  --vpc-security-group-ids "$SG" --db-subnet-group-name "$DB-subnets" --backup-retention-period 1 >/dev/null
echo "Aguardando o RDS ficar disponível (~10 min)..."
aws rds wait db-instance-available --db-instance-identifier "$DB"
HOST=$(aws rds describe-db-instances --db-instance-identifier "$DB" --query 'DBInstances[0].Endpoint.Address' --output text)
echo "RDS pronto. Implante com:"
echo "  DATABASE_HOST=$HOST ./k8s/deploy.sh   (com o mesmo DATABASE_PASSWORD exportado)"
