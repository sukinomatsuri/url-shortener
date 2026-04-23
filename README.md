# MiniLink — URL Shortener

A production-ready URL shortening service built with FastAPI + PostgreSQL, featuring a sleek Dark Glassmorphism frontend. The infrastructure is entirely provisioned on AWS using Terraform (IaC), and continuous deployment is automated via GitHub Actions (CI/CD).

Currently Live at: [http://13.212.205.51](http://13.212.205.51)

## Key Features

- **Blazing Fast API**: Powered by FastAPI (Python 3.12) and SQLAlchemy.
- **Premium User Interface**: A modern, responsive Single Page Application with a "Dark Glassmorphism" aesthetic.
- **Robust Database**: Uses PostgreSQL 16 on production and in-memory SQLite for rapid CI testing.
- **Automated CI/CD**: Zero-downtime deployment pipeline to Amazon EC2 via Docker Compose.
- **Infrastructure as Code**: One-click AWS environment setup (VPC, Security Groups, IAM, EC2, ECR) via Terraform.

---
## Tech Stack

| Layer | Technology |
|---|---|
| **Frontend** | HTML5, Vanilla CSS (Glassmorphism), JavaScript (Fetch API) |
| **Backend** | FastAPI, Python 3.12, Uvicorn |
| **Database** | PostgreSQL 16 |
| **Containerization**| Docker & Docker Compose (v2) |
| **Infrastructure** | Terraform >= 1.7 |
| **CI/CD** | GitHub Actions |
| **Cloud Provider** | AWS (EC2, ECR, IAM, VPC) |


