# ProBTP POC

A modern, cloud-native proof of concept application built with FastAPI, Next.js, and Google Cloud Platform.

## 🚀 Tech Stack

### Frontend

- **Next.js 15** with App Router
- **React 19** with TypeScript
- **shadcn/ui** components
- **Tailwind CSS** for styling
- **Bun** as package manager
- **Firebase Hosting** for deployment

### Backend

- **FastAPI** (Python 3.11+)
- **PostgreSQL** (Google Cloud SQL)
- **Redis** (Google Cloud Memorystore)
- **Docker** containerization
- **Google Cloud Run** for hosting

### Infrastructure

- **Google Cloud Platform** (GCP)
- **Firebase** (Auth, Hosting, Firestore)
- **Terraform** for Infrastructure as Code
- **GitHub Actions** for CI/CD

## 📁 Project Structure

```
probtp-poc/
├── backend/                  # FastAPI backend
│   ├── app/
│   │   ├── api/             # API endpoints
│   │   ├── core/            # Core configuration
│   │   ├── services/        # Business logic
│   │   ├── models/          # Data models
│   │   └── utils/           # Helper functions
│   ├── tests/               # Backend tests
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/                # Next.js frontend
│   ├── src/
│   │   ├── app/            # App router pages
│   │   ├── components/     # React components
│   │   ├── services/       # API services
│   │   └── utils/          # Utility functions
│   ├── public/             # Static assets
│   └── package.json
├── infrastructure/          # Infrastructure as Code
│   ├── terraform/          # Terraform configurations
│   └── scripts/            # Deployment scripts
├── .github/
│   └── workflows/          # CI/CD pipelines
├── docs/                   # Documentation
│   └── architecture/       # Architecture docs
├── firebase.json           # Firebase configuration
├── firestore.rules         # Firestore security rules
└── README.md
```

## 🛠️ Quick Start

### Prerequisites

- [Bun](https://bun.sh/) (latest)
- [Python 3.11+](https://python.org/)
- [Docker](https://docker.com/)
- [Google Cloud SDK](https://cloud.google.com/sdk)
- [Firebase CLI](https://firebase.google.com/docs/cli)
- [Terraform](https://terraform.io/) (v1.5.0+)

### Local Development

1. **Clone the repository**

   ```bash
   git clone <repository-url>
   cd probtp-poc
   ```

2. **Backend Setup**

   ```bash
   cd backend
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   uvicorn app.main:app --reload
   ```

3. **Frontend Setup**

   ```bash
   cd frontend
   bun install
   cp env.example .env.local
   # Edit .env.local with your Firebase config
   bun run dev
   ```

4. **Access the applications**
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000
   - API Docs: http://localhost:8000/docs

## 🔧 Configuration

### Environment Variables

Create these files with your configurations:

- `backend/.env` - Backend environment variables
- `frontend/.env.local` - Frontend environment variables

See `docs/setup.md` for detailed configuration instructions.

## 🚢 Deployment

### Infrastructure

```bash
cd infrastructure/terraform
terraform init
terraform plan
terraform apply
```

### Backend (Cloud Run)

```bash
cd backend
docker build -t gcr.io/your-project-id/probtp-poc-backend .
docker push gcr.io/your-project-id/probtp-poc-backend
# Deployment handled by GitHub Actions or Terraform
```

### Frontend (Firebase Hosting)

```bash
cd frontend
bun run build
firebase deploy --only hosting
```

## 🧪 Testing

### Backend Tests

```bash
cd backend
pytest tests/ -v
```

### Frontend Linting & Type Checking

```bash
cd frontend
bun run lint
bun run type-check
```

## 📋 Available Scripts

### Backend

- `uvicorn app.main:app --reload` - Start development server
- `pytest tests/ -v` - Run tests
- `black app/` - Format code
- `flake8 app/` - Lint code

### Frontend

- `bun run dev` - Start development server
- `bun run build` - Build for production
- `bun run start` - Start production server
- `bun run lint` - Run ESLint
- `bun run type-check` - Run TypeScript compiler

## 🏗️ Architecture

The application follows a modern microservices architecture:

- **Frontend**: Static Next.js app deployed to Firebase Hosting
- **Backend**: Containerized FastAPI app running on Google Cloud Run
- **Database**: PostgreSQL on Google Cloud SQL
- **Cache**: Redis on Google Cloud Memorystore
- **Authentication**: Firebase Authentication
- **Real-time**: Firestore for real-time features

See `docs/architecture/overview.md` for detailed architecture documentation.

## 🔐 Security

- JWT-based authentication via Firebase Auth
- CORS configuration for cross-origin requests
- Environment-based configuration management
- Firestore security rules for data access
- Docker containerization for isolation

## 📈 CI/CD

GitHub Actions workflows handle:

- **Code Quality**: Linting, type checking, testing
- **Infrastructure**: Terraform plan/apply
- **Backend**: Docker build/push, Cloud Run deployment
- **Frontend**: Build and Firebase Hosting deployment

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📚 Documentation

- [Setup Guide](docs/setup.md) - Detailed setup instructions
- [Architecture Overview](docs/architecture/overview.md) - System architecture
- [API Documentation](http://localhost:8000/docs) - Interactive API docs (when running locally)

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

For support and questions:

1. Check the [documentation](docs/)
2. Create an issue on GitHub
3. Review existing issues and discussions

---

**Built with ❤️ using modern web technologies**
