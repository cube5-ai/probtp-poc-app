# Setup Guide

## Prerequisites

- **Node.js** (for Bun installation)
- **Bun** (latest version)
- **Python 3.11+**
- **Docker** (for containerization)
- **Google Cloud SDK** (gcloud CLI)
- **Terraform** (v1.5.0+)
- **Firebase CLI**

## Local Development Setup

### 1. Clone and Setup

```bash
git clone <repository-url>
cd probtp-poc
```

### 2. Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create .env file
cp .env.example .env
# Edit .env with your configuration

# Run the application
uvicorn app.main:app --reload
```

The backend will be available at `http://localhost:8000`

### 3. Frontend Setup

```bash
cd frontend

# Install dependencies
bun install

# Create environment file
cp env.example .env.local
# Edit .env.local with your Firebase configuration

# Run the development server
bun run dev
```

The frontend will be available at `http://localhost:3000`

### 4. Database Setup

#### Option A: Local PostgreSQL

```bash
# Install PostgreSQL locally
# Create database
createdb probtp_poc_dev

# Update DATABASE_URL in backend/.env
DATABASE_URL=postgresql://username:password@localhost:5432/probtp_poc_dev
```

#### Option B: Cloud SQL Proxy

```bash
# Install Cloud SQL Proxy
gcloud auth login
gcloud sql connect your-instance --user=your-user
```

### 5. Redis Setup

#### Option A: Local Redis

```bash
# Install and start Redis locally
redis-server

# Update REDIS_URL in backend/.env
REDIS_URL=redis://localhost:6379
```

#### Option B: Cloud Memorystore

```bash
# Use gcloud proxy or VPC connection
```

## Firebase Setup

### 1. Create Firebase Project

```bash
# Install Firebase CLI
npm install -g firebase-tools

# Login to Firebase
firebase login

# Initialize Firebase in project root
firebase init
```

Select:

- Hosting
- Firestore
- Authentication

### 2. Configure Firebase

1. Go to Firebase Console
2. Enable Authentication providers
3. Set up Firestore rules
4. Get configuration keys
5. Update frontend/env.example with your keys

### 3. Firebase Emulators (Development)

```bash
# Start emulators
firebase emulators:start
```

## Google Cloud Setup

### 1. GCP Project Setup

```bash
# Create new project
gcloud projects create your-project-id

# Set project
gcloud config set project your-project-id

# Enable billing
gcloud billing projects link your-project-id --billing-account=BILLING_ACCOUNT_ID
```

### 2. Enable APIs

```bash
gcloud services enable run.googleapis.com
gcloud services enable sqladmin.googleapis.com
gcloud services enable redis.googleapis.com
gcloud services enable containerregistry.googleapis.com
gcloud services enable cloudbuild.googleapis.com
```

### 3. Service Account Setup

```bash
# Create service account
gcloud iam service-accounts create terraform-sa

# Grant permissions
gcloud projects add-iam-policy-binding your-project-id \
  --member="serviceAccount:terraform-sa@your-project-id.iam.gserviceaccount.com" \
  --role="roles/editor"

# Create and download key
gcloud iam service-accounts keys create terraform-key.json \
  --iam-account=terraform-sa@your-project-id.iam.gserviceaccount.com
```

## Infrastructure Deployment

### 1. Terraform Setup

```bash
cd infrastructure/terraform

# Initialize Terraform
terraform init

# Create terraform.tfvars
cat > terraform.tfvars << EOF
project_id = "your-project-id"
region = "us-central1"
environment = "dev"
db_password = "your-secure-password"
firebase_project_id = "your-firebase-project-id"
EOF

# Plan and apply
terraform plan
terraform apply
```

### 2. Backend Deployment

```bash
cd backend

# Build and push Docker image
docker build -t gcr.io/your-project-id/probtp-poc-backend .
docker push gcr.io/your-project-id/probtp-poc-backend

# Deploy to Cloud Run (done automatically via Terraform)
```

### 3. Frontend Deployment

```bash
cd frontend

# Build for production
bun run build

# Deploy to Firebase Hosting
firebase deploy --only hosting
```

## Environment Variables

### Backend (.env)

```
DATABASE_URL=postgresql://user:password@host:port/database
REDIS_URL=redis://host:port
SECRET_KEY=your-secret-key
ENVIRONMENT=development
```

### Frontend (.env.local)

```
NEXT_PUBLIC_FIREBASE_API_KEY=your-api-key
NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN=your-project.firebaseapp.com
NEXT_PUBLIC_FIREBASE_PROJECT_ID=your-project-id
NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET=your-project.appspot.com
NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID=your-sender-id
NEXT_PUBLIC_FIREBASE_APP_ID=your-app-id
NEXT_PUBLIC_API_URL=https://your-cloud-run-url.run.app
```

## GitHub Secrets

Configure these secrets in your GitHub repository:

- `GCP_PROJECT_ID`
- `GCP_SA_KEY` (base64 encoded service account key)
- `FIREBASE_SERVICE_ACCOUNT`
- `FIREBASE_PROJECT_ID`
- `DATABASE_URL`
- `REDIS_URL`
- `SECRET_KEY`
- `DB_PASSWORD`
- `NEXT_PUBLIC_FIREBASE_*` (all Firebase config)
- `NEXT_PUBLIC_API_URL`

## Testing

### Backend Tests

```bash
cd backend
pytest tests/ -v
```

### Frontend Tests

```bash
cd frontend
bun run lint
bun run type-check
```

## Troubleshooting

### Common Issues

1. **Build errors**: Check Node.js and Bun versions
2. **Database connection**: Verify DATABASE_URL and network access
3. **Firebase auth**: Check API keys and project configuration
4. **GCP permissions**: Verify service account has required roles
5. **Terraform state**: Ensure proper backend configuration

### Logs

- **Cloud Run logs**: `gcloud logs read --service=probtp-poc-backend`
- **Firebase logs**: `firebase functions:log`
- **Local logs**: Check terminal outputs
