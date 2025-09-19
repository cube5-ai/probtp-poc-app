# ProBTP POC Architecture Overview

## System Architecture

The ProBTP POC is built using a modern, cloud-native architecture with the following components:

### Frontend
- **Framework**: Next.js 15 with App Router
- **UI Library**: shadcn/ui components with Tailwind CSS
- **Package Manager**: Bun
- **Hosting**: Firebase Hosting
- **Authentication**: Firebase Auth

### Backend
- **Framework**: FastAPI (Python)
- **Database**: Google Cloud SQL (PostgreSQL)
- **Cache**: Google Cloud Memorystore (Redis)
- **Hosting**: Google Cloud Run
- **Container Registry**: Google Container Registry

### Infrastructure
- **Cloud Provider**: Google Cloud Platform (GCP)
- **Infrastructure as Code**: Terraform
- **Database**: Cloud SQL PostgreSQL
- **Authentication**: Firebase Authentication
- **File Storage**: Firebase Storage (if needed)
- **NoSQL Database**: Firestore (for real-time features)

## Architecture Diagram

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │    Backend      │    │  Infrastructure │
│  (Next.js)      │    │   (FastAPI)     │    │     (GCP)       │
├─────────────────┤    ├─────────────────┤    ├─────────────────┤
│ • React 19      │◄───┤ • Python 3.11   │◄───┤ • Cloud Run     │
│ • shadcn/ui     │    │ • FastAPI       │    │ • Cloud SQL     │
│ • Tailwind CSS  │    │ • PostgreSQL    │    │ • Redis         │
│ • Firebase Auth │    │ • Redis Cache   │    │ • Firebase      │
│ • Bun          │    │ • Docker        │    │ • Terraform     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                    ┌─────────────────┐
                    │   Firebase      │
                    │ • Hosting       │
                    │ • Authentication│
                    │ • Firestore     │
                    │ • Storage       │
                    └─────────────────┘
```

## Key Features

### Security
- Firebase Authentication for user management
- JWT token validation in FastAPI
- CORS configuration for cross-origin requests
- Environment-based configuration

### Scalability
- Containerized backend with Cloud Run auto-scaling
- CDN-delivered frontend via Firebase Hosting
- Database connection pooling
- Redis caching layer

### Development Experience
- Hot reloading for both frontend and backend
- TypeScript for type safety
- Modern UI components with shadcn/ui
- Comprehensive linting and formatting

### DevOps
- GitHub Actions for CI/CD
- Terraform for infrastructure management
- Automated testing and deployment
- Environment-specific configurations

## Development Workflow

1. **Local Development**
   - Frontend: `bun run dev` (localhost:3000)
   - Backend: `uvicorn app.main:app --reload` (localhost:8000)
   - Database: Local PostgreSQL or Cloud SQL proxy

2. **Testing**
   - Frontend: `bun run lint`, `bun run type-check`
   - Backend: `pytest`, `flake8`, `black`

3. **Deployment**
   - Infrastructure: Terraform apply
   - Backend: Docker build → GCR → Cloud Run
   - Frontend: Build → Firebase Hosting

## Environment Configuration

### Development
- Local PostgreSQL or Cloud SQL proxy
- Local Redis or Cloud Memorystore
- Firebase emulators for testing

### Production
- Cloud SQL PostgreSQL
- Cloud Memorystore Redis
- Firebase Authentication and Hosting
- Cloud Run for backend hosting
