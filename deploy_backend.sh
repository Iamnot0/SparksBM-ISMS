#!/bin/bash
set -e

# Colors for output
GREEN='\033[0;32m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== SparksBM Backend Deployer (GCP + Neon + Vercel) ===${NC}"
echo "This script deploys the Backend (Java/Python/Queue/Auth) to GKE."
echo "It skips the Frontend (on Vercel) and Database (on Neon)."

# 1. Check for Project ID
if [ -z "$1" ]; then
    echo "Please provide your Google Cloud Project ID."
    echo "Usage: ./deploy_backend.sh YOUR_PROJECT_ID"
    exit 1
fi

PROJECT_ID=$1
REGION="us-central1"
CLUSTER_NAME="sparksbm-cluster"

echo -e "${GREEN}Step 1: Setting Project to $PROJECT_ID...${NC}"
gcloud config set project $PROJECT_ID

# 2. Update K8s manifests with Project ID
echo -e "${GREEN}Step 2: Updating Kubernetes manifests...${NC}"
if [[ "$OSTYPE" == "darwin"* ]]; then
  sed -i '' "s/PROJECT_ID_PLACEHOLDER/$PROJECT_ID/g" k8s/*.yaml
else
  sed -i "s/PROJECT_ID_PLACEHOLDER/$PROJECT_ID/g" k8s/*.yaml
fi

# 3. Create Artifact Registry
echo -e "${GREEN}Step 3: Creating Artifact Registry (if not exists)...${NC}"
gcloud artifacts repositories create sparksbm-repo \
    --repository-format=docker \
    --location=$REGION \
    --description="Docker repository for SparksBM" || echo "Repo might already exist, continuing..."

# 4. Build Images (Backend Only)
echo -e "${GREEN}Step 4: Building Backend Images...${NC}"
# We submit the SAME cloudbuild.yaml, but the Frontend/Postgres steps are harmless (or we can just let them run).
# To save time, we should probably have a backend-only build.
# For now, we will use the existing build - it will just overwrite the artifact registry with the same code.
gcloud builds submit --config cloudbuild.yaml .

# 5. Create GKE Cluster
echo -e "${GREEN}Step 5: Creating GKE Autopilot Cluster...${NC}"
gcloud container clusters create-auto $CLUSTER_NAME \
    --region $REGION || echo "Cluster might already exist, getting credentials..."

# 6. Get Cluster Credentials
echo -e "${GREEN}Step 6: Configuring kubectl...${NC}"
gcloud container clusters get-credentials $CLUSTER_NAME --region $REGION

# 7. Deploy Services (Skipping Postgres and Frontend)
echo -e "${GREEN}Step 7: Deploying Backend Services to Kubernetes...${NC}"
echo "Deploying RabbitMQ & Keycloak..."
kubectl apply -f k8s/rabbitmq.yaml
kubectl apply -f k8s/keycloak.yaml

echo "Waiting for infrastructure to stabilize (10s)..."
sleep 10

echo "Deploying APIs..."
kubectl apply -f k8s/sparksbm-app.yaml
kubectl apply -f k8s/notebook-api.yaml

# Note: We do NOT deploy k8s/postgres.yaml (using Neon) or k8s/notebook-frontend.yaml (using Vercel)

echo -e "${GREEN}=== Backend Deployment Complete! ===${NC}"
echo "Your backend is running on GKE and connecting to Neon."
echo "Check pods: kubectl get pods"
