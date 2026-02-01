#!/bin/bash
set -e

# Colors for output
GREEN='\033[0;32m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== SparksBM Google Cloud Deployer ===${NC}"
echo "This script will help you deploy your project to GKE."

# 1. Check for Project ID
if [ -z "$1" ]; then
    echo "Please provide your Google Cloud Project ID."
    echo "Usage: ./deploy_to_gcp.sh YOUR_PROJECT_ID"
    exit 1
fi

PROJECT_ID=$1
REGION="us-central1"
CLUSTER_NAME="sparksbm-cluster"

echo -e "${GREEN}Step 1: Setting Project to $PROJECT_ID...${NC}"
gcloud config set project $PROJECT_ID

# 2. Update K8s manifests with Project ID
echo -e "${GREEN}Step 2: Updating Kubernetes manifests...${NC}"
# MacOS compatibility for sed
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

# 4. Build Images
echo -e "${GREEN}Step 4: Building Container Images (this may take a while)...${NC}"
# We assume cloudbuild.yaml uses $PROJECT_ID variable, which Cloud Build handles automatically.
# However, we need to make sure the tags match what we put in the K8s files.
# In k8s files: gcr.io/$PROJECT_ID/...
# In cloudbuild.yaml: gcr.io/$PROJECT_ID/...
# Cloud Build will substitute $PROJECT_ID automatically.
gcloud builds submit --config cloudbuild.yaml .

# 5. Create GKE Cluster
echo -e "${GREEN}Step 5: Creating GKE Autopilot Cluster (if not exists)...${NC}"
gcloud container clusters create-auto $CLUSTER_NAME \
    --region $REGION || echo "Cluster might already exist, getting credentials..."

# 6. Get Cluster Credentials
echo -e "${GREEN}Step 6: Configuring kubectl...${NC}"
gcloud container clusters get-credentials $CLUSTER_NAME --region $REGION

# 7. Deploy Services
echo -e "${GREEN}Step 7: Deploying Services to Kubernetes...${NC}"
echo "Deploying Infrastructure (Postgres, RabbitMQ, Keycloak)..."
kubectl apply -f k8s/postgres.yaml
kubectl apply -f k8s/rabbitmq.yaml
kubectl apply -f k8s/keycloak.yaml

echo "Waiting for infrastructure to stabilize (10s)..."
sleep 10

echo "Deploying Apps..."
kubectl apply -f k8s/sparksbm-app.yaml
kubectl apply -f k8s/notebook-api.yaml
kubectl apply -f k8s/notebook-frontend.yaml

echo -e "${GREEN}=== Deployment Complete! ===${NC}"
echo "Check the status of your pods with: kubectl get pods"
echo "Get the external IP of your frontend with: kubectl get service notebook-frontend"
