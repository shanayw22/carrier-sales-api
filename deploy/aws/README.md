# AWS ECS/Fargate Deployment

This is the reproducible deployment document for the current AWS setup. Use it when you want something cleaner than the original ad-hoc console walkthrough.

This guide sets up the backend on AWS with:

- ECR for the container image
- RDS PostgreSQL for the database
- ECS Fargate for the API service
- ALB for a public URL

Account ID is prefilled as `696741019085`.

## Prerequisites

- AWS CLI installed and authenticated with an IAM principal that can manage ECR, ECS, ELBv2, RDS, EC2 security groups, IAM, and CloudWatch Logs
- A VPC with:
  - two public subnets for the ALB
  - two private subnets for ECS tasks and RDS
- Docker installed locally

This environment currently does not have AWS credentials configured, so the commands below are prepared but cannot be executed from here until `aws configure` or equivalent credentials are available.

## Current State And Remaining Hardening

- The stack is currently deployed on AWS behind an ALB.
- HTTPS is live on the ALB.
- Custom domain is `https://api.hrsubs.dev`.
- HTTP `:80` redirects to HTTPS `:443`.
- The dashboard shell is public, while metrics and business endpoints still require `X-API-Key`.

## Reproduction Flow

Use this order to reproduce the deployment from scratch:

1. Create or confirm the VPC, public subnets, private subnets, NAT gateway, and route tables.
2. Create the ALB, ECS, and RDS security groups.
3. Create the RDS instance and note the endpoint.
4. Create Secrets Manager secrets for `API_KEY`, `FMCSA_API_KEY`, and `DATABASE_URL`.
5. Push the `linux/amd64` container image to ECR.
6. Create the ECS cluster, task execution role, task definition, and ECS service.
7. Point the ECS service at the ALB target group and verify `/health` and `/dashboard/`.
8. Attach ACM to the ALB, add the HTTPS listener, and redirect HTTP to HTTPS.
9. Add the Route 53 alias for `api.hrsubs.dev`.

## 1. Set Variables

Run these in your shell first and replace the placeholder values:

```bash
export ACCOUNT_ID=696741019085
export AWS_REGION=us-east-2

export VPC_ID=vpc-xxxxxxxx
export PUBLIC_SUBNET_1=subnet-public1
export PUBLIC_SUBNET_2=subnet-public2
export PRIVATE_SUBNET_1=subnet-private1
export PRIVATE_SUBNET_2=subnet-private2

export DB_SUBNET_GROUP=carrier-sales-db-subnet
export DB_IDENTIFIER=carrier-sales-db
export DB_NAME=postgres
export DB_USERNAME=admin_db
export DB_PASSWORD='replace-with-strong-password'

export APP_API_KEY='replace-with-your-production-api-key'
export FMCSA_API_KEY='replace-with-your-working-fmcsa-key'
```

## 2. Push the Image to ECR

```bash
aws ecr create-repository \
  --repository-name carrier-sales-api \
  --region "$AWS_REGION"

aws ecr get-login-password --region "$AWS_REGION" | \
  docker login --username AWS --password-stdin \
  "$ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com"

docker build -t carrier-sales-api .

docker tag carrier-sales-api:latest \
  "$ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/carrier-sales-api:latest"

docker push \
  "$ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/carrier-sales-api:latest"

# For Apple Silicon hosts, publish the runtime architecture ECS expects.
docker buildx build \
  --platform linux/amd64 \
  -t "$ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/carrier-sales-api:latest" \
  --push .
```

## 3. Create Security Groups

Create the ALB and ECS groups first, then create the RDS group so it can reference the ECS group.

```bash
ALB_SG=$(aws ec2 create-security-group \
  --group-name carrier-alb-sg \
  --description "ALB public access" \
  --vpc-id "$VPC_ID" \
  --query 'GroupId' --output text)

aws ec2 authorize-security-group-ingress \
  --group-id "$ALB_SG" \
  --protocol tcp --port 80 --cidr 0.0.0.0/0

aws ec2 authorize-security-group-ingress \
  --group-id "$ALB_SG" \
  --protocol tcp --port 443 --cidr 0.0.0.0/0

ECS_SG=$(aws ec2 create-security-group \
  --group-name carrier-ecs-sg \
  --description "ECS from ALB only" \
  --vpc-id "$VPC_ID" \
  --query 'GroupId' --output text)

aws ec2 authorize-security-group-ingress \
  --group-id "$ECS_SG" \
  --protocol tcp --port 8000 --source-group "$ALB_SG"

RDS_SG=$(aws ec2 create-security-group \
  --group-name carrier-rds-sg \
  --description "RDS from ECS only" \
  --vpc-id "$VPC_ID" \
  --query 'GroupId' --output text)

aws ec2 authorize-security-group-ingress \
  --group-id "$RDS_SG" \
  --protocol tcp --port 5432 --source-group "$ECS_SG"
```

## 4. Create the RDS PostgreSQL Instance

```bash
aws rds create-db-subnet-group \
  --db-subnet-group-name "$DB_SUBNET_GROUP" \
  --db-subnet-group-description "Carrier sales DB" \
  --subnet-ids "$PRIVATE_SUBNET_1" "$PRIVATE_SUBNET_2"

aws rds create-db-instance \
  --db-instance-identifier "$DB_IDENTIFIER" \
  --db-instance-class db.t3.micro \
  --engine postgres \
  --engine-version 16 \
  --master-username "$DB_USERNAME" \
  --master-user-password "$DB_PASSWORD" \
  --allocated-storage 20 \
  --vpc-security-group-ids "$RDS_SG" \
  --db-subnet-group-name "$DB_SUBNET_GROUP" \
  --no-publicly-accessible

aws rds wait db-instance-available \
  --db-instance-identifier "$DB_IDENTIFIER"

RDS_ENDPOINT=$(aws rds describe-db-instances \
  --db-instance-identifier "$DB_IDENTIFIER" \
  --query 'DBInstances[0].Endpoint.Address' \
  --output text)

export RDS_ENDPOINT
printf 'RDS endpoint: %s\n' "$RDS_ENDPOINT"
```

Use a `DATABASE_URL` secret in this format once the instance is available:

```text
postgresql://admin_db:YOUR_RDS_PASSWORD@YOUR_RDS_ENDPOINT:5432/postgres?sslmode=require
```

## 5. Create the ALB and Target Group

```bash
TG_ARN=$(aws elbv2 create-target-group \
  --name carrier-sales-tg \
  --protocol HTTP --port 8000 \
  --vpc-id "$VPC_ID" \
  --target-type ip \
  --health-check-path /health \
  --query 'TargetGroups[0].TargetGroupArn' --output text)

ALB_ARN=$(aws elbv2 create-load-balancer \
  --name carrier-sales-alb \
  --subnets "$PUBLIC_SUBNET_1" "$PUBLIC_SUBNET_2" \
  --security-groups "$ALB_SG" \
  --query 'LoadBalancers[0].LoadBalancerArn' --output text)

aws elbv2 create-listener \
  --load-balancer-arn "$ALB_ARN" \
  --protocol HTTP --port 80 \
  --default-actions Type=forward,TargetGroupArn="$TG_ARN"
```

## 6. Create the ECS Cluster and Execution Role

```bash
aws ecs create-cluster --cluster-name carrier-sales

aws iam create-role \
  --role-name ecsTaskExecutionRole \
  --assume-role-policy-document '{
    "Version": "2012-10-17",
    "Statement": [
      {
        "Effect": "Allow",
        "Principal": {"Service": "ecs-tasks.amazonaws.com"},
        "Action": "sts:AssumeRole"
      }
    ]
  }'

aws iam attach-role-policy \
  --role-name ecsTaskExecutionRole \
  --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy
```

If the role already exists, skip the `create-role` call and only ensure the managed policy is attached.

## 7. Render and Register the Task Definition

From the repo root:

```bash
chmod +x deploy/aws/render-task-definition.sh

ACCOUNT_ID="$ACCOUNT_ID" \
AWS_REGION="$AWS_REGION" \
DB_PASSWORD="$DB_PASSWORD" \
RDS_ENDPOINT="$RDS_ENDPOINT" \
APP_API_KEY="$APP_API_KEY" \
FMCSA_API_KEY="$FMCSA_API_KEY" \
deploy/aws/render-task-definition.sh

aws ecs register-task-definition \
  --cli-input-json file://deploy/aws/task-definition.json
```

## 8. Create the ECS Service

```bash
aws ecs create-service \
  --cluster carrier-sales \
  --service-name carrier-sales-api \
  --task-definition carrier-sales-api \
  --desired-count 1 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[$PRIVATE_SUBNET_1,$PRIVATE_SUBNET_2],securityGroups=[$ECS_SG],assignPublicIp=DISABLED}" \
  --load-balancers "targetGroupArn=$TG_ARN,containerName=api,containerPort=8000"
```

## 9. Verify the Public URL

```bash
ALB_DNS=$(aws elbv2 describe-load-balancers \
  --names carrier-sales-alb \
  --query 'LoadBalancers[0].DNSName' --output text)

curl "http://$ALB_DNS/health"

curl -H "X-API-Key: $APP_API_KEY" \
  "http://$ALB_DNS/carriers?mc_number=1234567"

curl -H "X-API-Key: $APP_API_KEY" \
  "http://$ALB_DNS/loads/ABC12345"
```

For the current live deployment, verify:

```bash
curl https://api.hrsubs.dev/health

curl -H "X-API-Key: $APP_API_KEY" \
  "https://api.hrsubs.dev/carriers?mc_number=1234567"

curl -H "X-API-Key: $APP_API_KEY" \
  "https://api.hrsubs.dev/metrics/dashboard"
```

## Still Needed From You

I can take this further once you have these values:

- VPC ID
- two public subnet IDs
- two private subnet IDs
- whether you want to keep the public dashboard shell or move it behind auth
*** Add File: /Users/shanaywadhwani/Desktop/HRai/carrier-sales-api/PROSPECT_EMAIL_DRAFT.md
Subject: Carrier Sales Automation Prototype Update

To: c.becker@happyrobot.ai
Cc: recruiter@happyrobot.ai

Hi Carlos,

Ahead of our meeting, I wanted to share the latest progress on the inbound carrier sales automation prototype.

Current status:

- Built and deployed a FastAPI backend to AWS ECS/Fargate with HTTPS enabled at `https://api.hrsubs.dev`
- Implemented inbound carrier vetting through the FMCSA-backed carrier lookup flow
- Implemented load retrieval through a broker-controlled load API backed by a structured load dataset
- Added a completed-call webhook that stores call outcomes and negotiation metadata in PostgreSQL
- Built a live dashboard for custom metrics, including booking rate, negotiation activity, rate outcomes, lane mix, and recent calls
- Added deployment documentation and a reproducible AWS deployment path

The current workflow supports the core inbound use case:

1. Carrier provides MC number
2. System verifies carrier details
3. System retrieves the requested load
4. Agent negotiates pricing
5. Final call outcome is written into the metrics backend and surfaced in the dashboard

Live assets:

- API: `https://api.hrsubs.dev`
- Dashboard: `https://api.hrsubs.dev/dashboard/`

For the meeting, I can walk through the workflow setup, show the live demo, and explain the deployment and reporting architecture.

Best,

Shanay Wadhwani
*** Add File: /Users/shanaywadhwani/Desktop/HRai/carrier-sales-api/BROKER_BUILD_DESCRIPTION.md
# Carrier Sales Automation Build Description

Prepared for: Acme Logistics

## Overview

This build is a prototype for automating inbound carrier calls related to load booking. The system is designed to verify carriers, retrieve load information, negotiate pricing, and capture operational metrics from every completed conversation.

## Use Case

When a carrier calls in, the agent:

1. requests the MC number
2. verifies the carrier through an FMCSA-backed lookup flow
3. requests the broker reference or load identifier
4. retrieves structured load details from the broker load API
5. negotiates pricing within the workflow
6. transfers or closes the call based on the booking outcome
7. writes completed call data into the reporting backend

## System Components

- Inbound HappyRobot workflow for the call logic
- Carrier verification API for MC lookup
- Load lookup API backed by a broker-managed load dataset
- Completed-call webhook for analytics ingestion
- PostgreSQL database for metrics persistence
- Live dashboard for reporting and QA review

## Deployment

- Cloud provider: AWS
- Runtime: ECS Fargate
- Database: PostgreSQL on RDS
- HTTPS endpoint: `https://api.hrsubs.dev`
- Dashboard: `https://api.hrsubs.dev/dashboard/`

## Security

- HTTPS is enabled for deployed traffic
- Business endpoints require API key authentication via `X-API-Key`
- Secrets are injected through AWS Secrets Manager in deployment

## Dashboard Metrics

The dashboard supports custom reporting beyond the workflow itself, including:

- booking rate
- negotiation rounds
- call duration
- final agreed rate
- lane distribution
- recent call history
- sentiment mix

## Prototype Scope

For the prototype, load data is served from a structured broker-owned dataset exposed through an API. In production, the same interface could be backed by a TMS, internal database, or another load management service.

## Operational Notes

- The completed-call webhook is idempotent by `call_id`
- Workflow retries update the same record rather than creating duplicates
- Dashboard metrics can be reset for clean demo runs

## Outcome

This prototype demonstrates a workable inbound carrier sales flow with both operational automation and a reporting layer suitable for internal review, QA, and broker-side visibility.