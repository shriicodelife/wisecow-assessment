# Wisecow Assessment

A production-ready containerization, orchestration, continuous delivery (CI/CD), and operational monitoring solution for the **Wisecow** application.

---

## 📁 Repository Structure

```text
wisecow-assessment/
├── Dockerfile                      # Production Dockerfile for Wisecow
├── wisecow.sh                      # Core Wisecow web application script
├── k8s/                            # Kubernetes Manifests
│   ├── deployment.yaml             # Deployment configuration (2 replicas, health probes, non-root)
│   ├── service.yaml                # ClusterIP service exposing port 80 -> 4499
│   └── ingress-tls.yaml            # Ingress rule with TLS termination & cert-manager
├── .github/
│   └── workflows/
│       └── ci-cd.yml               # GitHub Actions workflow for linting, build & push to GHCR
├── scripts/                        # Operational & Monitoring Scripts
│   ├── system_health_monitor.py    # System health monitor (CPU, Memory, Disk, Processes)
│   └── app_health_checker.py       # Application uptime & HTTP health checker
└── README.md                       # Complete setup and operational documentation
```

---

## 🚀 Problem Statements Covered

| Component | Description | Implementation |
| :--- | :--- | :--- |
| **Problem 1: Containerization** | Dockerize `wisecow.sh` securely | Minimal Ubuntu base, non-root user (`10001`), `cowsay`/`fortune-mod` in `/usr/games` |
| **Problem 1: Kubernetes** | Orchestration manifests | Zero-downtime rolling update deployment, ClusterIP service, resource limits, health checks |
| **Problem 1: Secure TLS** | TLS/HTTPS ingress integration | Kubernetes Ingress with `cert-manager` Let's Encrypt cluster-issuer & TLS termination |
| **Problem 1: CI/CD Pipeline** | Automated build & deploy | GitHub Actions with ShellCheck, flake8, manifest dry-run, and GHCR Docker publishing |
| **Problem 2: System Monitor** | Linux system health monitoring | `scripts/system_health_monitor.py` checking CPU, RAM, Disk, and Process thresholds |
| **Problem 2: App Health Check** | Application uptime monitoring | `scripts/app_health_checker.py` checking HTTP availability, latency, and status codes |

---

## 🛠️ Prerequisites

- **Docker** 20.10+
- **Kubectl** v1.26+
- **Minikube** or **Kind** (for local Kubernetes testing)
- **Python** 3.9+ (for monitoring scripts)
- Ingress controller (e.g., `ingress-nginx`) and `cert-manager` (for TLS challenge)

---

## 🐳 Step 1: Containerization with Docker

The application runs a lightweight HTTP server serving ASCII fortune cows on port `4499`.

### 1. Build the Docker Image
```bash
docker build -t wisecow:latest .
```

### 2. Run the Container
```bash
docker run -d -p 4499:4499 --name wisecow-app wisecow:latest
```

### 3. Verify Local Execution
Open your browser or run:
```bash
curl http://localhost:4499
```
*Expected Output: ASCII cow rendering a dynamic fortune message.*

---

## ☸️ Step 2: Kubernetes Deployment & Ingress TLS

All manifests reside in the [`k8s/`](file:///k8s/) directory.

### 1. Deploy the Application & Service
```bash
# Apply deployment and service
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml

# Verify pod status and rollout
kubectl rollout status deployment/wisecow-deployment
kubectl get pods -l app.kubernetes.io/name=wisecow
kubectl get svc wisecow-service
```

### 2. Configure Ingress with TLS (Cert-Manager)
Ensure Ingress Nginx and Cert-Manager are enabled on your cluster:

```bash
# If using minikube:
minikube addons enable ingress

# Deploy cert-manager (if not present)
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.13.0/cert-manager.yaml

# Apply Ingress configuration
kubectl apply -f k8s/ingress-tls.yaml
```

To test locally with custom hosts, add `wisecow.example.com` to your `/etc/hosts` or `C:\Windows\System32\drivers\etc\hosts`:
```text
127.0.0.1 wisecow.example.com
```
Then visit:
```bash
curl -k https://wisecow.example.com
```

---

## 🔄 Step 3: CI/CD Pipeline (GitHub Actions)

The pipeline is defined in [`.github/workflows/ci-cd.yml`](file:///.github/workflows/ci-cd.yml) and runs automatically on every `push` and `pull_request` to the `main` branch:

1. **Lint & Validation Stage**:
   - ShellCheck validates `wisecow.sh`.
   - Flake8 checks the Python scripts in `scripts/`.
   - `kubectl apply --dry-run=client` validates all Kubernetes manifests.
2. **Build & Push Stage**:
   - Multi-arch Docker Buildx builds the container.
   - Pushes the image to GitHub Container Registry (`ghcr.io/shriicodelife/wisecow`).
   - Automatically tags with `latest` and commit SHA `sha-xxxxxxx`.
3. **Security Scan Stage**:
   - Runs Trivy vulnerability scanner on the container image for High and Critical vulnerabilities.

---

## 📊 Step 4: Operational & Monitoring Scripts

### 1. System Health Monitoring Script (`scripts/system_health_monitor.py`)
Monitors CPU, Memory, Disk, and Process count with configurable alert thresholds.

```bash
# Run one-time health check (exits with summary)
python scripts/system_health_monitor.py

# Run with custom alert thresholds (e.g. CPU > 75%, Memory > 80%, Disk > 85%)
python scripts/system_health_monitor.py --cpu-threshold 75 --mem-threshold 80 --disk-threshold 85

# Run continuously as a background daemon checking every 30 seconds
python scripts/system_health_monitor.py --interval 30 --log-file /var/log/system_health.log
```

**Features**:
- Fallbacks to `/proc` and `shutil` if `psutil` is not installed.
- Logs events with timestamps to both console and `system_health.log`.
- Identifies and logs top CPU-consuming processes when an alert fires.

---

### 2. Application Health Checker (`scripts/app_health_checker.py`)
Monitors web application uptime, response latency, and HTTP status codes.

```bash
# One-time health check against the application
python scripts/app_health_checker.py --url http://localhost:4499

# Continuous monitoring every 10 seconds with 3s timeout
python scripts/app_health_checker.py --url http://localhost:4499 --interval 10 --timeout 3.0

# Integration with Kubernetes Ingress
python scripts/app_health_checker.py --url https://wisecow.example.com --expected-status 200
```

**Features**:
- Zero external dependencies (uses standard library `urllib`).
- Configurable retry count and request timeouts.
- Distinguishes between HTTP errors (4xx/5xx), network connection failures, and timeouts.
- Exit code `0` on healthy, `1` on failure (ready for alerting/cron integration).

---

## 🔒 Security Best Practices Implemented

- **Non-Root Execution**: Container runs as dedicated user `appuser` (UID `10001`).
- **Minimal Image Surface**: Installed packages are limited to runtime requirements with apt cache cleared.
- **Resource Constraints**: Pods specify explicit CPU and Memory requests and limits to prevent noisy-neighbor issues.
- **Liveness & Readiness Probes**: Kubernetes automatically restarts hung containers and only routes traffic to ready pods.
- **Automated Security Scanning**: Trivy scanner is integrated into the CI/CD pipeline to detect vulnerabilities before release.
