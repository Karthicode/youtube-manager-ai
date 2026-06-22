# Kubernetes Migration: YouTube Manager AI

A complete reference for the migration of YouTube Manager AI from Vercel serverless
to a local Kubernetes cluster running on minikube. Covers every concept, command,
decision, and gotcha encountered along the way.

---

## Table of Contents

1. [What Changed and Why](#1-what-changed-and-why)
2. [Architecture Overview](#2-architecture-overview)
3. [Core Kubernetes Concepts](#3-core-kubernetes-concepts)
4. [Step 1 — Dockerize the Backend](#4-step-1--dockerize-the-backend)
5. [Step 2 — Dockerize the Frontend](#5-step-2--dockerize-the-frontend)
6. [Step 3 — Local Cluster with Minikube](#6-step-3--local-cluster-with-minikube)
7. [Step 4 — Build Images into Minikube](#7-step-4--build-images-into-minikube)
8. [Step 5 — PostgreSQL StatefulSet](#8-step-5--postgresql-statefulset)
9. [Step 6 — Redis StatefulSet](#9-step-6--redis-statefulset)
10. [Step 7 — Kubernetes Secrets](#10-step-7--kubernetes-secrets)
11. [Step 8 — ConfigMap](#11-step-8--configmap)
12. [Step 9 — Backend Deployment](#12-step-9--backend-deployment)
13. [Step 10 — Frontend Deployment](#13-step-10--frontend-deployment)
14. [Step 11 — Ingress](#14-step-11--ingress)
15. [Step 12 — Full Stack Verification](#15-step-12--full-stack-verification)
16. [Step 13 — Scaling and HPA](#16-step-13--scaling-and-hpa)
17. [Step 14 — Helm Chart](#17-step-14--helm-chart)
18. [Flow Charts](#18-flow-charts)
19. [Commands Cheatsheet](#19-commands-cheatsheet)
20. [Troubleshooting Guide](#20-troubleshooting-guide)

---

## 1. What Changed and Why

### Before: Vercel Serverless

```
Browser
  └── Vercel CDN ──► Next.js (serverless functions, auto-scaled by Vercel)
                          └── FastAPI (serverless via index.py)
                                  └── Neon PostgreSQL (managed cloud)
                                  └── Upstash Redis (managed cloud)
```

**Limitations of the serverless model:**
- Every request spins up a cold function — slow first requests after idle
- No persistent connections to the database (connection pooling is hard)
- No long-running background tasks (function timeout ≤ 10s on free tier)
- No control over infrastructure — Vercel decides where and how things run
- SSE (Server-Sent Events) for streaming responses has timeout constraints

### After: Kubernetes on Minikube

```
Browser
  └── /etc/hosts ──► 127.0.0.1 (youtube-manager.local)
                          └── minikube tunnel ──► nginx Ingress Controller
                                  ├── /api/* ──► backend-svc ──► FastAPI pods
                                  ├── /mcp/*  ──► backend-svc ──► FastAPI pods
                                  └── /*      ──► frontend-svc ──► Next.js pods
                                                        │
                                               Pods share cluster DNS:
                                                  ├── postgres:5432
                                                  └── redis:6379
```

**What Kubernetes gives you:**
- Always-running pods — no cold starts
- Persistent TCP connections to Postgres and Redis
- Health-probe-based self-healing (crashed pod → automatically restarted)
- Declarative config — the desired state is in YAML files, K8s enforces it
- Horizontal scaling via HPA
- Rolling deployments with zero downtime

---

## 2. Architecture Overview

### Full Resource Map

```
Namespace: default
│
├── Ingress: youtube-manager-ingress
│     nginx.ingress.kubernetes.io/proxy-body-size: 50m
│     nginx.ingress.kubernetes.io/proxy-read-timeout: 300
│     Rules:
│       youtube-manager.local/api  ──► backend-svc:8000
│       youtube-manager.local/mcp  ──► backend-svc:8000
│       youtube-manager.local/     ──► frontend-svc:3000
│
├── Deployments (stateless, rolling update strategy)
│     ├── backend   (replicas: 1, managed by HPA 1–5)
│     │     init container: run-migrations (alembic upgrade head)
│     │     main container: uvicorn app.main:app --port 8000
│     │     envFrom: ConfigMap/app-config
│     │     env: Secret/app-secrets (individual keys)
│     │
│     └── frontend  (replicas: 1)
│           main container: node server.js (Next.js standalone)
│           no env injection — NEXT_PUBLIC_API_URL baked at build time
│
├── StatefulSets (stateful, stable identity + persistent storage)
│     ├── postgres  ──► PVC: postgres-pvc (5Gi)
│     └── redis     ──► PVC: redis-pvc (1Gi)
│
├── Services (stable DNS + load balancing)
│     ├── backend-svc   ClusterIP  port 8000
│     ├── frontend-svc  ClusterIP  port 3000
│     ├── postgres      Headless   port 5432
│     └── redis         Headless   port 6379
│
├── ConfigMap: app-config
│     ENVIRONMENT, REDIS_URL, ALGORITHM, OPENAI_MODEL,
│     CORS_ORIGINS, YOUTUBE_REDIRECT_URI, FRONTEND_URL, BACKEND_URL
│
├── Secret: app-secrets
│     postgres-password, secret-key, openai-api-key,
│     youtube-client-id, youtube-client-secret,
│     qstash-token, qstash-current-signing-key, qstash-next-signing-key
│
└── HPA: backend-hpa
      target: deployment/backend
      minReplicas: 1, maxReplicas: 5
      CPU trigger: 70%, Memory trigger: 150%
```

### File Layout

```
youtube-manager-ai/
├── backend/
│   ├── Dockerfile           multi-stage: builder + runtime
│   └── .dockerignore
├── frontend/
│   ├── Dockerfile           multi-stage: deps + builder + runner
│   ├── .dockerignore
│   └── next.config.ts       output: 'standalone' added
└── k8s/
    ├── postgres/
    │   ├── statefulset.yaml
    │   ├── pvc.yaml
    │   └── service.yaml
    ├── redis/
    │   ├── statefulset.yaml
    │   ├── pvc.yaml
    │   └── service.yaml
    ├── secrets/
    │   └── create-secrets.sh.example   imperative script (real values gitignored)
    ├── configmap/
    │   └── app-config.yaml
    ├── backend/
    │   ├── deployment.yaml   init container + main container + probes + resources
    │   ├── service.yaml
    │   └── hpa.yaml
    ├── frontend/
    │   ├── deployment.yaml
    │   └── service.yaml
    ├── ingress/
    │   └── ingress.yaml
    └── helm/
        └── youtube-manager/
            ├── Chart.yaml
            ├── values.yaml
            ├── secrets.values.yaml.example
            └── templates/
                ├── _helpers.tpl
                ├── configmap.yaml
                ├── secret.yaml
                ├── backend/   deployment.yaml  service.yaml  hpa.yaml
                ├── frontend/  deployment.yaml  service.yaml
                ├── postgres/  statefulset.yaml pvc.yaml      service.yaml
                ├── redis/     statefulset.yaml pvc.yaml      service.yaml
                └── ingress/   ingress.yaml
```

---

## 3. Core Kubernetes Concepts

### The Control Loop

Kubernetes works entirely on **desired state vs actual state**:

1. You write a YAML manifest declaring what you want (e.g., "3 replicas of this image")
2. You `kubectl apply` it — this stores the desired state in `etcd` (K8s database)
3. The relevant controller constantly compares desired ↔ actual
4. If they differ, the controller acts to reconcile them (create pods, restart crashed containers, etc.)

This means K8s is self-healing by design — if you delete a pod manually, the controller sees "1 actual, 3 desired" and creates a new one within seconds.

### Pod

The smallest deployable unit. A pod wraps one or more containers that share:
- A network namespace (same IP, same localhost)
- The same lifecycle (start and stop together)

Pods are **ephemeral** — they can be killed and replaced at any time. Never store state inside a pod.

### Deployment vs StatefulSet

| | Deployment | StatefulSet |
|---|---|---|
| **Use for** | Stateless apps (backend, frontend) | Stateful apps (databases, queues) |
| **Pod identity** | Random names (`backend-abc123`) | Stable ordinal names (`postgres-0`) |
| **Storage** | Shared or none | Each pod gets its own PVC |
| **Scaling** | All pods are identical | Ordered scale-up/down |
| **Rolling update** | Kill old, start new | Sequential, one at a time |

### Service

A stable network endpoint that load-balances across all healthy pods matching a label selector.

```
Pod 1 (app=backend)  ┐
Pod 2 (app=backend)  ├── Service: backend-svc  ◄── other pods / Ingress
Pod 3 (app=backend)  ┘     ClusterIP: 10.x.x.x:8000
```

**ClusterIP** (regular): Virtual IP, load-balances. Used for stateless Deployments.
**Headless** (`clusterIP: None`): No virtual IP. DNS returns the pod IPs directly. Used for StatefulSets because the app often needs to connect to a specific pod (`postgres-0`), not just any pod.

### ConfigMap vs Secret

Both inject configuration into pods. The difference is intent and storage:

| | ConfigMap | Secret |
|---|---|---|
| **For** | Non-sensitive config | Passwords, tokens, keys |
| **Storage** | Plain text in etcd | Base64-encoded in etcd |
| **Injection** | `envFrom`, `env`, volume mount | Same, plus `secretKeyRef` |

> Base64 is **encoding, not encryption**. Secrets are not secure by default — they require RBAC and etcd encryption at rest for real security. The separation still matters for access control and audit trails.

### PersistentVolumeClaim (PVC)

A request for storage that survives pod restarts and rescheduling. Think of it as a reservation:

```
PVC (what you ask for)          PV (what K8s provisions)
  storageClassName: standard  ──► minikube's hostPath provisioner
  storage: 5Gi                     /tmp/hostpath/postgres-pvc
  accessModes: ReadWriteOnce
```

`ReadWriteOnce` = only one node can mount it at a time (fine for single-replica databases).

### Init Container

A container that runs to completion **before** the main container starts.

```
Pod start sequence:
  init container 1 (run-migrations) ──exits 0──► main container starts
                                    ──exits 1──► pod retries (with backoff)
```

Used here to run `alembic upgrade head` so the database schema is always up-to-date before FastAPI starts. If the migration fails, the pod never starts — preventing a broken app from serving traffic.

### Readiness vs Liveness Probes

| | Readiness Probe | Liveness Probe |
|---|---|---|
| **Question** | "Is this pod ready to receive traffic?" | "Is this pod still alive?" |
| **Failing action** | Removed from Service load balancer | Pod is killed and restarted |
| **Use for** | Slow startup, warm-up period | Deadlock detection |

Both use `httpGet /health :8000` in this project. The health endpoint checks DB + Redis connectivity.

### Ingress

An HTTP/HTTPS routing layer on top of Services. A single entry point that dispatches to multiple backends based on hostname and path.

```
Ingress resource (config)         Ingress controller (nginx pod)
  host: youtube-manager.local       Running in kube-system namespace
  /api → backend-svc:8000           Reads Ingress resources via K8s API
  /mcp → backend-svc:8000           Configures nginx routing rules
  /    → frontend-svc:3000          Handles actual HTTP proxying
```

The Ingress **resource** is just YAML. The Ingress **controller** is what actually does the work — a long-running nginx pod installed via `minikube addons enable ingress`.

---

## 4. Step 1 — Dockerize the Backend

### Why Multi-Stage Builds

Without multi-stage builds, the final image contains the compiler, build tools, and all intermediate files. Multi-stage builds throw away everything except what the app needs to run.

```dockerfile
# Stage 1: builder — has pip, compilers, etc.
FROM python:3.11-slim AS builder
WORKDIR /install
COPY requirements.txt .
RUN pip install --prefix=/install --no-cache-dir -r requirements.txt

# Stage 2: runtime — only the installed packages + app code
FROM python:3.11-slim
COPY --from=builder /install /usr/local
COPY app/ /app/app/
COPY alembic/ /app/alembic/
COPY alembic.ini /app/
WORKDIR /app
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
```

### Key Decisions

**`python:3.11-slim` not `alpine`:** `psycopg2-binary` requires `libpq`. The `slim` variant includes it; `alpine` does not — installing it from source on alpine adds complexity and build time.

**Include `alembic/` and `alembic.ini`:** The init container (Step 9) runs `alembic upgrade head` inside this image. If those files are missing, migrations fail.

**`.dockerignore`** prevents `.env*`, `__pycache__`, `.venv`, `tests/`, `index.py`, `vercel.json` from being sent to the build context (speeds up builds, keeps secrets out of images).

### Commands

```bash
# Build
docker build -t youtube-manager-backend:dev ./backend

# Test locally (requires a real database)
docker run --rm -p 8000:8000 \
  -e SECRET_KEY=x \
  -e DATABASE_URL=postgresql://postgres:postgres@host.docker.internal:5432/youtube_manager \
  -e REDIS_URL=redis://host.docker.internal:6379/0 \
  -e YOUTUBE_CLIENT_ID=x \
  -e YOUTUBE_CLIENT_SECRET=x \
  -e OPENAI_API_KEY=x \
  youtube-manager-backend:dev

# Verify
curl localhost:8000/health
```

---

## 5. Step 2 — Dockerize the Frontend

### Build-Time vs Runtime Environment Variables

This is the most important concept for Next.js in containers.

`NEXT_PUBLIC_*` variables are **inlined at build time** into the JavaScript bundle. Once the bundle is built, the value is baked in — changing an environment variable at runtime has no effect.

```
Wrong mental model:
  docker run -e NEXT_PUBLIC_API_URL=http://new-url  ← has NO effect

Correct model:
  docker build --build-arg NEXT_PUBLIC_API_URL=http://youtube-manager.local/api/v1
               ← baked into the JS bundle forever
```

**Why `http://youtube-manager.local/api/v1`?**
The browser makes API calls. The browser is on your Mac, not inside the cluster. It cannot resolve `http://backend-svc:8000` (internal cluster DNS). It CAN resolve `youtube-manager.local` because of the `/etc/hosts` entry pointing to `127.0.0.1`, which `minikube tunnel` routes into the cluster.

### `output: 'standalone'` in next.config.ts

Without this, `npm run build` produces a full Next.js installation that requires `node_modules/` to run — hundreds of MB. With `standalone`, Next.js traces all required files and copies only them into `.next/standalone/`, producing a self-contained `server.js`. Image size drops dramatically.

### Three-Stage Dockerfile

```dockerfile
# Stage 1: deps — install node_modules (cached unless package-lock changes)
FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --omit=dev

# Stage 2: builder — compile TypeScript, run Next.js build
FROM node:20-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ARG NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
RUN npm run build

# Stage 3: runner — only the standalone output
FROM node:20-alpine AS runner
WORKDIR /app
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public
CMD ["node", "server.js"]
```

### Commands

```bash
# Build (NEXT_PUBLIC_API_URL must be the Ingress hostname)
docker build \
  --build-arg NEXT_PUBLIC_API_URL=http://youtube-manager.local/api/v1 \
  -t youtube-manager-frontend:dev \
  ./frontend

# Test
docker run --rm -p 3000:3000 youtube-manager-frontend:dev
```

---

## 6. Step 3 — Local Cluster with Minikube

### What Minikube Creates

Minikube runs a single-node Kubernetes cluster inside a Docker container (on macOS with the Docker driver). That one container acts as both the control plane (API server, etcd, scheduler, controller-manager) and a worker node.

```
Your Mac
  └── Docker Desktop
        └── minikube container (192.168.49.2)
              ├── kube-apiserver
              ├── etcd
              ├── kube-scheduler
              ├── kube-controller-manager
              └── kubelet (runs your pods)
```

### Why `minikube tunnel` is Required on macOS

minikube with the Docker driver is isolated inside a Docker network. Kubernetes `LoadBalancer` services (which the nginx Ingress controller uses) get an IP in that network (`192.168.49.2`), not on your Mac's `127.0.0.1`.

`minikube tunnel` creates a network route so that traffic to the LoadBalancer IP is forwarded to `127.0.0.1`. This is why `/etc/hosts` uses `127.0.0.1`, not `192.168.49.2`.

```
Browser → youtube-manager.local → 127.0.0.1:80
                                        ↓
                              minikube tunnel
                                        ↓
                              nginx Ingress pod at 192.168.49.2
```

`minikube tunnel` must run in a dedicated terminal for the entire session. It requires sudo (binds to port 80).

### Setup Commands

```bash
# Install tools (macOS)
brew install minikube kubectl helm

# Start cluster
minikube start --cpus=4 --memory=4096 --disk-size=20g --driver=docker

# Enable add-ons
minikube addons enable ingress          # nginx Ingress controller
minikube addons enable metrics-server   # required for HPA

# Run in a DEDICATED terminal (keep running)
minikube tunnel

# Add DNS entry (once per machine)
echo "127.0.0.1  youtube-manager.local" | sudo tee -a /etc/hosts

# Verify
kubectl cluster-info
kubectl get nodes
```

---

## 7. Step 4 — Build Images into Minikube

### The `eval $(minikube docker-env)` Pattern

By default, `docker build` builds into Docker Desktop's daemon. Kubernetes pods pull images from the Kubernetes node's daemon — a completely separate Docker. The two don't share images.

`eval $(minikube docker-env)` sets shell environment variables (`DOCKER_HOST`, etc.) that redirect all `docker` commands in the current shell to minikube's daemon instead.

```bash
# This shell now talks to minikube's Docker daemon
eval $(minikube docker-env)

# Builds go INTO minikube — not Docker Desktop
docker build -t youtube-manager-backend:dev ./backend
docker build --build-arg NEXT_PUBLIC_API_URL=http://youtube-manager.local/api/v1 \
  -t youtube-manager-frontend:dev ./frontend

# Verify images are visible to K8s
docker images | grep youtube-manager
```

### `imagePullPolicy: Never`

Every Deployment and StatefulSet manifest that uses a local image must include:

```yaml
imagePullPolicy: Never
```

Without this, Kubernetes tries to pull the image from Docker Hub, fails with `ErrImagePull`, and the pod never starts. `Never` tells K8s: "this image must already exist on the node — do not attempt to pull it."

> Re-run `eval $(minikube docker-env)` in every new terminal. It is only set for the current shell session.

---

## 8. Step 5 — PostgreSQL StatefulSet

### Why StatefulSet (Not Deployment)

A Deployment's pods are interchangeable. K8s can create pod `backend-abc` and replace it with `backend-xyz` — that's fine for stateless apps. But a database pod needs:

1. A **stable hostname** — so other pods can always find it at `postgres-0`
2. A **dedicated PVC** — so its data disk moves with it, not shared with other replicas

StatefulSets provide both. Pod `postgres-0` always gets the same name and always mounts `postgres-pvc`.

### Headless Service (`clusterIP: None`)

Regular Services have a virtual IP that load-balances across pods. For a database, you usually want to connect to a specific pod (`postgres-0`), not any random pod. A headless service (`clusterIP: None`) skips the virtual IP entirely — DNS returns the pod's actual IP.

```yaml
spec:
  clusterIP: None    # headless
  selector:
    app: postgres
```

DNS: `postgres.default.svc.cluster.local` → `postgres-0`'s IP directly.

### PVC (PersistentVolumeClaim)

The PVC is a storage request. minikube's `standard` StorageClass fulfills it automatically using `hostPath` (a directory on the minikube node).

```yaml
spec:
  accessModes:
    - ReadWriteOnce   # one node can mount at a time (fine for single-replica DB)
  storageClassName: standard
  resources:
    requests:
      storage: 5Gi
```

**Critical:** PVCs outlive pods. If you delete the StatefulSet, the PVC remains. Reapply the StatefulSet and it reattaches to the existing PVC with all data intact. To wipe data you must delete the PVC explicitly.

### Commands

```bash
kubectl apply -f k8s/postgres/

# Wait for postgres to be ready
kubectl wait --for=condition=ready pod/postgres-0 --timeout=120s

# Verify
kubectl exec -it statefulset/postgres -- psql -U postgres -c "\l"
```

---

## 9. Step 6 — Redis StatefulSet

Same pattern as PostgreSQL. Key differences:

**Command override** — Redis needs AOF persistence enabled:
```yaml
command: ["redis-server", "--appendonly", "yes", "--dir", "/data"]
```
Without `--appendonly yes`, Redis only keeps data in memory — a pod restart loses everything.

**Readiness probe:**
```yaml
readinessProbe:
  exec:
    command: ["redis-cli", "ping"]
```
Redis responds with `PONG` when ready.

### Commands

```bash
kubectl apply -f k8s/redis/
kubectl wait --for=condition=ready pod/redis-0 --timeout=60s
kubectl exec -it statefulset/redis -- redis-cli ping   # → PONG
```

---

## 10. Step 7 — Kubernetes Secrets

### Why Imperative Creation

Two ways to create Secrets:

**Declarative** (in a YAML file):
```yaml
apiVersion: v1
kind: Secret
stringData:
  openai-api-key: sk-real-key-here   # ← this would end up in git
```
This is dangerous — secrets end up committed to the repository.

**Imperative** (via kubectl):
```bash
kubectl create secret generic app-secrets \
  --from-literal=openai-api-key="sk-real-key-here"
```
Values never touch a file. They go directly to the K8s API and are stored in etcd (base64-encoded). Nothing to accidentally commit.

The pattern used here: a `create-secrets.sh.example` script documents what keys exist (with placeholder values), committed to git. The real `create-secrets.sh` (with actual values) is in `.gitignore`.

### Variable Substitution in Deployments

`DATABASE_URL` embeds the postgres password. Rather than hardcoding it, K8s supports `$(VAR_NAME)` substitution within a pod's `env` list:

```yaml
env:
  # Step 1: inject the password from the Secret into an env var
  - name: POSTGRES_PASSWORD
    valueFrom:
      secretKeyRef:
        name: app-secrets
        key: postgres-password

  # Step 2: use it via substitution — K8s replaces $(POSTGRES_PASSWORD) at runtime
  - name: DATABASE_URL
    value: "postgresql://postgres:$(POSTGRES_PASSWORD)@postgres:5432/youtube_manager"
```

**Order matters:** `POSTGRES_PASSWORD` must appear before `DATABASE_URL` in the list. K8s processes env vars in order — a reference to a var that hasn't been defined yet resolves to an empty string.

### Commands

```bash
# Create (or update — dry-run+apply pattern is idempotent)
kubectl create secret generic app-secrets \
  --from-literal=postgres-password=postgres \
  --from-literal=secret-key="$(openssl rand -hex 32)" \
  --from-literal=openai-api-key="sk-..." \
  --from-literal=youtube-client-id="..." \
  --from-literal=youtube-client-secret="..." \
  --from-literal=qstash-token="" \
  --from-literal=qstash-current-signing-key="" \
  --from-literal=qstash-next-signing-key="" \
  --dry-run=client -o yaml | kubectl apply -f -

# Inspect (values are base64-encoded)
kubectl get secret app-secrets -o yaml

# Decode a specific value
kubectl get secret app-secrets -o jsonpath='{.data.openai-api-key}' | base64 -d
```

### Gotcha: Secrets Are Destroyed with the Cluster

`minikube delete` destroys etcd and all its contents — including Secrets. Keep `create-secrets.sh` (gitignored) locally so you can recreate them on a fresh cluster.

---

## 11. Step 8 — ConfigMap

Non-sensitive configuration. Injected in bulk via `envFrom`:

```yaml
envFrom:
  - configMapRef:
      name: app-config   # injects ALL keys as env vars
```

### `CORS_ORIGINS` Gotcha

pydantic-settings v2 reads `list[str]` fields from JSON format, not comma-separated strings:

```yaml
# WRONG — pydantic-settings raises SettingsError
CORS_ORIGINS: "http://youtube-manager.local,http://localhost:3000"

# CORRECT — valid JSON array
CORS_ORIGINS: '["http://youtube-manager.local","http://localhost:3000"]'
```

### `DATABASE_URL` Is Intentionally Absent

`DATABASE_URL` contains the postgres password. It cannot go in a ConfigMap (plaintext). It cannot go in a Secret (it contains a non-secret hostname). The correct approach is construction in the Deployment via `$(POSTGRES_PASSWORD)` substitution — see Step 7.

### Commands

```bash
kubectl apply -f k8s/configmap/app-config.yaml

# Updating ConfigMap does NOT automatically restart pods
# Must trigger a rollout manually:
kubectl rollout restart deployment/backend
```

---

## 12. Step 9 — Backend Deployment

### Init Container Pattern

```
Pod spec:
  initContainers:
    - name: run-migrations        ← runs first, must exit 0
      command: ["python", "-m", "alembic", "upgrade", "head"]
  containers:
    - name: backend               ← starts only after init exits 0
      command: uvicorn ...
```

**Why:** If the main container started before migrations, FastAPI might serve requests against a schema that doesn't match the code. The init container acts as a gate — no traffic until the schema is correct.

**Concurrent migrations (multiple replicas):** When scaling to 3 replicas, all 3 init containers run `alembic upgrade head` simultaneously. Alembic uses a PostgreSQL advisory lock — only one migration runs at a time, the others wait and then exit successfully (nothing to do).

### `CREATE INDEX CONCURRENTLY` Requires Autocommit

PostgreSQL cannot create an index concurrently inside a transaction. Alembic wraps all migrations in a transaction by default.

```python
# WRONG — will fail with:
# "CREATE INDEX CONCURRENTLY cannot run inside a transaction block"
op.execute("CREATE INDEX CONCURRENTLY ...")

# CORRECT — step outside Alembic's implicit transaction
with op.get_context().autocommit_block():
    op.execute("CREATE INDEX CONCURRENTLY ...")
```

### Resource Requests vs Limits

```yaml
resources:
  requests:          # scheduler reserves this on the node
    cpu: "250m"      # 250 millicores = 0.25 of a core
    memory: "400Mi"  # set based on kubectl top pods observation
  limits:            # hard cap — pod is OOMKilled if exceeded
    cpu: "1000m"     # 1 full core burst
    memory: "768Mi"
```

**Critical:** HPA calculates utilization as `actual usage / requests`. If requests are set too low (e.g., 256Mi when the app actually uses 386Mi), the HPA sees 150% utilization and keeps scaling up even under zero load. Always set requests based on observed usage from `kubectl top pods`.

### Commands

```bash
kubectl apply -f k8s/backend/

# Watch migrations run
kubectl logs -l app=backend -c run-migrations

# Check pod status
kubectl get pods -l app=backend

# Verify health endpoint
kubectl port-forward svc/backend-svc 8000:8000
curl http://localhost:8000/health
# → {"status":"healthy","database":"connected","redis":"connected"}
```

---

## 13. Step 10 — Frontend Deployment

The simplest manifest in the project. No env injection needed — `NEXT_PUBLIC_API_URL` was baked at image build time.

### Why No `env:` or `envFrom:`

At container start, `node server.js` reads the pre-built JavaScript bundle. That bundle already has `http://youtube-manager.local/api/v1` embedded as a string constant. There is no mechanism for Next.js to re-read `NEXT_PUBLIC_*` env vars from the container environment at runtime.

Non-`NEXT_PUBLIC_*` vars (used in server-side code) can be injected at runtime — but this project has none.

### Commands

```bash
kubectl apply -f k8s/frontend/
kubectl rollout status deployment/frontend --timeout=120s

# Verify
kubectl port-forward svc/frontend-svc 3001:3000
# Open browser: http://localhost:3001
```

---

## 14. Step 11 — Ingress

### Ingress Resource vs Ingress Controller

A common source of confusion:

| | Ingress Resource | Ingress Controller |
|---|---|---|
| **What it is** | A YAML config file you write | A running pod (nginx) |
| **What it does** | Declares routing rules | Actually proxies HTTP traffic |
| **Who reads it** | Ingress Controller watches it | Reads from K8s API |
| **How to install** | `kubectl apply -f ingress.yaml` | `minikube addons enable ingress` |

The Ingress Resource is inert config. The Ingress Controller is the execution engine.

### Path Ordering

nginx matches paths **in order, top to bottom**. More specific paths must come first:

```yaml
paths:
  - path: /api        # matched first — specific
  - path: /mcp        # matched second — specific
  - path: /           # matched last — catch-all
```

If `/` came first, every request (including `/api/v1/...`) would go to the frontend.

### Annotations

```yaml
annotations:
  nginx.ingress.kubernetes.io/proxy-body-size: "50m"       # for large uploads
  nginx.ingress.kubernetes.io/proxy-read-timeout: "300"    # for SSE streaming
  nginx.ingress.kubernetes.io/proxy-send-timeout: "300"    # for SSE streaming
```

Without the timeout annotations, nginx closes SSE connections after 60 seconds (default), which breaks the sync progress stream.

### Commands

```bash
kubectl apply -f k8s/ingress/
kubectl get ingress youtube-manager-ingress   # wait for ADDRESS to appear

# End-to-end tests
curl http://youtube-manager.local/api/v1/docs    # Swagger UI
curl -I http://youtube-manager.local/            # Next.js 200
```

---

## 15. Step 12 — Full Stack Verification

### Cluster State Snapshot

```bash
kubectl get all                              # everything in default namespace
kubectl get ingress                          # ingress + address
kubectl get events --sort-by='.lastTimestamp'  # recent events, chronological
kubectl top pods                             # live CPU/memory
kubectl top nodes                            # node resource pressure
```

### Connectivity Matrix

| From | To | How |
|---|---|---|
| Browser | youtube-manager.local | /etc/hosts → 127.0.0.1 |
| 127.0.0.1:80 | nginx pod | minikube tunnel |
| nginx | backend-svc | ClusterIP Service |
| nginx | frontend-svc | ClusterIP Service |
| FastAPI pod | postgres | Headless Service DNS |
| FastAPI pod | redis | Headless Service DNS |
| K8s kubelet | FastAPI pod /health | Direct pod IP (probes) |

---

## 16. Step 13 — Scaling and HPA

### Manual Scaling

```bash
# Scale up
kubectl scale deployment/backend --replicas=3

# Watch pods come up in real time
kubectl get pods -l app=backend -w

# Scale back down
kubectl scale deployment/backend --replicas=1
```

What happens during scale-up:
1. Controller sees desired=3, actual=1 → creates 2 new pods
2. Each new pod runs the init container (Alembic — exits quickly, nothing to do)
3. Main container starts, passes readiness probe
4. Service starts routing traffic to new pods
5. Zero downtime — the original pod never stopped

### HPA (Horizontal Pod Autoscaler)

```yaml
spec:
  scaleTargetRef:
    kind: Deployment
    name: backend
  minReplicas: 1
  maxReplicas: 5
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70    # scale when avg CPU > 70% of requests
    - type: Resource
      resource:
        name: memory
        target:
          type: Utilization
          averageUtilization: 150   # scale when avg memory > 150% of requests
```

**HPA decision loop** (runs every 15 seconds):
1. Query metrics-server for current CPU/memory of all backend pods
2. Calculate desired replicas: `ceil(current_replicas * (current_metric / target_metric))`
3. Apply stabilization windows (prevent thrashing)
4. Set Deployment replicas to the new count

**Stabilization windows:**
- Scale up: 60s — don't add more than 2 pods per 60s window
- Scale down: 300s — only scale down after 5 minutes of sustained low usage

This prevents "flapping": a brief spike shouldn't cause immediate scale-up then immediate scale-down.

### Key Lesson: Set Requests Accurately

The memory requests were initially `256Mi`, but `kubectl top pods` showed actual usage of `386Mi`. This caused the HPA to see 150% utilization and scale to max replicas even at idle. The fix was raising requests to `400Mi` (slightly above observed baseline).

```bash
# Observe actual usage before setting requests
kubectl top pods -l app=backend

# Check HPA decisions
kubectl describe hpa backend-hpa
kubectl get hpa backend-hpa -w   # watch in real time
```

---

## 17. Step 14 — Helm Chart

### Why Helm

Without Helm, changing the domain name means editing 6+ files: configmap, ingress, frontend deployment (if the build arg were injected), and documentation. With Helm:

```bash
helm upgrade youtube-manager k8s/helm/youtube-manager/ \
  -f secrets.values.yaml \
  --set domain=my-other-domain.local
```

One flag updates every resource that references `{{ .Values.domain }}`.

### Chart Structure

```
Chart.yaml        — metadata (name, version, appVersion)
values.yaml       — all tunable defaults, no secrets
secrets.values.yaml.example  — documents secret keys, gitignored copy holds real values
templates/
  _helpers.tpl    — reusable template snippets (labels, DATABASE_URL)
  configmap.yaml  — {{ .Values.config.* }} and {{ .Values.domain }}
  secret.yaml     — {{ .Values.secrets.* }} (passed at deploy time)
  backend/        — deployment, service, hpa
  frontend/       — deployment, service
  postgres/       — statefulset, pvc, service
  redis/          — statefulset, pvc, service
  ingress/        — ingress
```

### Template Syntax

```yaml
# Simple value
replicas: {{ .Values.backend.replicas }}

# With default fallback
image: {{ .Values.backend.image.repository | default "youtube-manager-backend" }}

# Quote strings (prevents YAML parsing issues with special chars)
memory: {{ .Values.backend.resources.requests.memory | quote }}

# Conditional block
{{- if .Values.hpa.enabled }}
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
...
{{- end }}

# Indented include (nindent = newline + N spaces of indent)
labels:
  {{- include "youtube-manager.labels" . | nindent 4 }}
```

### The `_helpers.tpl` Pattern

```
{{- define "youtube-manager.labels" -}}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}
```

Define once, use in every resource with `{{- include "youtube-manager.labels" . | nindent 4 }}`. Changing the label structure means editing one place.

### Deploying

```bash
# Lint (catch syntax errors before deploying)
helm lint k8s/helm/youtube-manager/ \
  --set secrets.postgresPassword=test \
  --set secrets.secretKey=test \
  --set secrets.openaiApiKey=test \
  --set secrets.youtubeClientId=test \
  --set secrets.youtubeClientSecret=test

# Dry run (see rendered YAML without deploying)
helm template youtube-manager k8s/helm/youtube-manager/ \
  -f secrets.values.yaml

# Deploy (install or upgrade)
helm upgrade --install youtube-manager k8s/helm/youtube-manager/ \
  -f k8s/helm/youtube-manager/secrets.values.yaml \
  --rollback-on-failure --timeout 3m

# Check release status
helm list
helm status youtube-manager
helm history youtube-manager   # all revisions

# Roll back to previous revision
helm rollback youtube-manager 1

# Tear down (keeps PVCs by default — data is preserved)
helm uninstall youtube-manager
```

### Adopting Existing Resources into Helm

If resources were originally created with `kubectl apply` (not Helm), Helm refuses to manage them. Fix by adding ownership metadata:

```bash
kubectl label secret app-secrets app.kubernetes.io/managed-by=Helm --overwrite
kubectl annotate secret app-secrets \
  meta.helm.sh/release-name=youtube-manager \
  meta.helm.sh/release-namespace=default \
  --overwrite
```

Repeat for each resource. Then `helm upgrade --install --force` succeeds.

---

## 18. Flow Charts

### 18.1 — Full Request Flow (Browser to Database)

```
User browser (Mac)
        │
        │  GET http://youtube-manager.local/api/v1/videos
        ▼
/etc/hosts resolves → 127.0.0.1
        │
        ▼
minikube tunnel (port 80 on 127.0.0.1)
        │
        ▼
nginx Ingress Controller pod (kube-system namespace)
        │
        │  host=youtube-manager.local, path=/api → backend-svc:8000
        ▼
Service: backend-svc (ClusterIP 10.x.x.x:8000)
        │
        │  load-balances across pods with label app=backend
        ▼
Pod: backend-xxxxx
  FastAPI (uvicorn, port 8000)
        │
        ├──► SQLAlchemy → Service: postgres (headless) → postgres-0:5432
        │                                                        │
        │                                              PVC: postgres-pvc
        │                                          (hostPath on minikube node)
        │
        └──► redis-py → Service: redis (headless) → redis-0:6379
                                                           │
                                                    PVC: redis-pvc
```

### 18.2 — Pod Startup Lifecycle

```
kubectl apply -f deployment.yaml
        │
        ▼
Scheduler assigns pod to node
        │
        ▼
kubelet pulls image (imagePullPolicy: Never → already on node)
        │
        ▼
┌───────────────────────────────────┐
│        Init Container             │
│   python -m alembic upgrade head  │
│                                   │
│   exit 0 ──────────────────────┐  │
│   exit 1 → pod restarts (backoff) │
└───────────────────────────────────┘
        │ exit 0
        ▼
┌───────────────────────────────────┐
│        Main Container             │
│   uvicorn app.main:app            │
│                                   │
│   Readiness probe: GET /health    │
│   ├── fail → not in Service LB    │
│   └── pass → added to Service LB  │
│                                   │
│   Liveness probe: GET /health     │
│   └── fail 3x → pod is restarted  │
└───────────────────────────────────┘
```

### 18.3 — HPA Scaling Decision Loop

```
Every 15 seconds:
        │
        ▼
metrics-server collects CPU/memory from all backend pods
        │
        ▼
HPA controller calculates:
  desiredReplicas = ceil(currentReplicas × (actualMetric / targetMetric))

  e.g., CPU: ceil(1 × (140% / 70%)) = ceil(2.0) = 2
  e.g., Mem: ceil(1 × (93% / 150%)) = ceil(0.62) = 1  ← scale down

  Final = max(cpuDesired, memDesired) = 2
        │
        ├── desiredReplicas > currentReplicas?
        │         │
        │         ▼
        │   scaleUp.stabilizationWindowSeconds: 60
        │   max 2 pods per 60s window
        │         │
        │         ▼
        │   kubectl scale deployment/backend --replicas=2
        │
        └── desiredReplicas < currentReplicas?
                  │
                  ▼
            scaleDown.stabilizationWindowSeconds: 300
            Must sustain lower metric for 5 minutes
                  │
                  ▼
            kubectl scale deployment/backend --replicas=1
```

### 18.4 — Helm Upgrade Lifecycle

```
helm upgrade --install youtube-manager ./chart -f secrets.values.yaml
        │
        ▼
Helm renders all templates → 13 Kubernetes YAML objects
        │
        ▼
Helm compares with previous release (stored in K8s Secret)
  ├── New resources → kubectl apply (create)
  ├── Changed resources → kubectl apply (update)
  └── Removed resources → kubectl delete
        │
        ▼
Helm waits for Deployments to roll out (--rollback-on-failure)
        │
        ├── All ready → STATUS: deployed, REVISION: N
        │
        └── Timeout/error → helm rollback (reverts to REVISION: N-1)
```

### 18.5 — Secrets Flow

```
Developer machine (gitignored file)
  create-secrets.sh
        │
        │ kubectl create secret generic app-secrets --from-literal=...
        ▼
Kubernetes etcd (base64-encoded)
  Secret: app-secrets
        │
        │ secretKeyRef in Deployment spec
        ▼
Pod environment variable
  OPENAI_API_KEY = "sk-..." (decoded, plaintext in pod memory)
        │
        │ os.getenv() or pydantic-settings
        ▼
Application code
  settings.openai_api_key
```

---

## 19. Commands Cheatsheet

### Cluster Management

```bash
minikube start --cpus=4 --memory=4096 --driver=docker
minikube stop
minikube delete                    # destroys everything including etcd (Secrets)
minikube status
minikube tunnel                    # run in dedicated terminal, keep alive
eval $(minikube docker-env)        # redirect docker to minikube's daemon
minikube ssh                       # shell into the minikube node
```

### Inspecting Resources

```bash
kubectl get all                          # pods, services, deployments, replicasets
kubectl get pods -l app=backend          # filter by label
kubectl get pods -o wide                 # includes node and IP columns
kubectl get events --sort-by='.lastTimestamp'
kubectl describe pod <pod-name>          # full detail: events, mounts, probes
kubectl describe deployment backend
kubectl top pods                         # live CPU/memory (requires metrics-server)
kubectl top nodes
```

### Logs

```bash
kubectl logs <pod-name>                  # main container logs
kubectl logs <pod-name> -c run-migrations   # specific container
kubectl logs -l app=backend              # all pods matching label
kubectl logs -l app=backend --follow     # tail -f style
kubectl logs <pod-name> --previous       # logs from the crashed previous container
```

### Deploying

```bash
kubectl apply -f k8s/backend/            # apply all files in directory
kubectl apply -f k8s/                    # recursive if -R flag added
kubectl rollout restart deployment/backend   # trigger rolling restart
kubectl rollout status deployment/backend    # wait for rollout completion
kubectl rollout undo deployment/backend      # revert to previous ReplicaSet
kubectl rollout history deployment/backend   # show revision history
```

### Scaling

```bash
kubectl scale deployment/backend --replicas=3
kubectl get hpa backend-hpa -w           # watch HPA in real time
kubectl describe hpa backend-hpa         # show scaling events and reasons
```

### Debugging

```bash
# Shell into a running pod
kubectl exec -it <pod-name> -- /bin/bash
kubectl exec -it statefulset/postgres -- psql -U postgres

# Port-forward for local testing
kubectl port-forward svc/backend-svc 8000:8000
kubectl port-forward svc/frontend-svc 3001:3000
kubectl port-forward statefulset/postgres 5433:5432

# Copy files from pod
kubectl cp <pod>:/path/to/file ./local-file
```

### Helm

```bash
helm lint ./chart                        # syntax check
helm template ./chart -f secrets.yaml    # render YAML (dry run)
helm upgrade --install <release> ./chart -f secrets.yaml
helm list                                # all releases
helm status <release>                    # current release state
helm history <release>                   # revision history
helm rollback <release> <revision>       # revert to a past revision
helm uninstall <release>                 # delete all release resources
helm get values <release>                # show deployed values
helm get manifest <release>              # show deployed YAML
```

### Resource Cleanup

```bash
# Delete specific resources
kubectl delete deployment backend
kubectl delete pod <pod-name>

# Delete by label (dangerous — matches all pods with that label)
kubectl delete pods -l app=backend

# Delete everything in a directory of manifests
kubectl delete -f k8s/backend/

# Nuclear option: delete entire namespace
kubectl delete namespace default         # DO NOT DO THIS — default is special
```

---

## 20. Troubleshooting Guide

### Pod Won't Start

| Symptom | Command to diagnose | Likely cause |
|---|---|---|
| `ErrImagePull` | `kubectl describe pod` | Missing `imagePullPolicy: Never` |
| `ErrImageNeverPull` | `kubectl describe pod` | Image not built into minikube daemon |
| `Init:CrashLoopBackOff` | `kubectl logs <pod> -c run-migrations` | Migration failure |
| `CrashLoopBackOff` | `kubectl logs <pod> --previous` | App startup error |
| `Pending` | `kubectl describe pod` → Events | Insufficient node resources or missing Secret |
| `0/1 Running` (not Ready) | `kubectl describe pod` → Readiness probe | App not responding on health endpoint |

### Migration Failures

```bash
# See the actual error
kubectl logs <backend-pod> -c run-migrations

# Common errors:
# "NameError: name 'sa' is not defined" → add "import sqlalchemy as sa"
# "relation already exists" → add if_not_exists=True to op.create_index()
# "CREATE INDEX CONCURRENTLY cannot run inside a transaction"
#   → wrap in: with op.get_context().autocommit_block():
# "password authentication failed" → Secret has wrong password for existing DB
```

### Backend Not Responding (502)

```bash
kubectl get pods -l app=backend               # check if Running
kubectl describe pod -l app=backend           # check probe status
kubectl logs -l app=backend                   # check startup errors

# pydantic-settings SettingsError for list fields:
# ConfigMap value must be JSON array, not comma-separated:
# CORS_ORIGINS: '["http://a.com","http://b.com"]'   ← correct
# CORS_ORIGINS: "http://a.com,http://b.com"          ← wrong for pydantic v2
```

### Can't Reach `youtube-manager.local`

```bash
# 1. Check tunnel is running
ps aux | grep "minikube tunnel"

# 2. Check /etc/hosts
grep "youtube-manager.local" /etc/hosts   # must be 127.0.0.1

# 3. Check ingress got an address
kubectl get ingress youtube-manager-ingress   # ADDRESS column

# 4. Check nginx controller is running
kubectl get pods -n kube-system | grep ingress
```

### Database Issues

```bash
# Connect directly
kubectl exec -it statefulset/postgres -- psql -U postgres

# Check if DB exists
kubectl exec -it statefulset/postgres -- \
  psql -U postgres -c "\l" | grep youtube_manager

# If collation mismatch after cluster recreation:
kubectl exec -it statefulset/postgres -- psql -U postgres -c "
  CREATE DATABASE youtube_manager
  TEMPLATE template0
  LC_COLLATE 'en_US.utf8'
  LC_CTYPE 'en_US.utf8';
"

# Reset password if auth fails (unix socket bypasses auth):
kubectl exec -it statefulset/postgres -- \
  psql -U postgres -c "ALTER USER postgres WITH PASSWORD 'postgres';"
```

### HPA Keeps Scaling Up

```bash
# Check actual usage vs requests
kubectl top pods -l app=backend
kubectl describe hpa backend-hpa   # shows current metric values

# Fix: raise requests to match actual observed usage
# In deployment.yaml:
# resources.requests.memory: "400Mi"   ← set to observed baseline + 10%
```

### Node Memory Pressure

```bash
kubectl top nodes    # > 85% is a warning

# Reduce replicas that are idle
kubectl scale deployment/backend --replicas=1
kubectl delete hpa backend-hpa   # temporarily disable auto-scaling

# Or increase minikube memory:
minikube stop
minikube start --memory=6144
```

---

## Application Deploy Order (Fresh Cluster)

```bash
# 1. Start cluster and tunnel
minikube start --cpus=4 --memory=4096 --driver=docker
minikube addons enable ingress
minikube addons enable metrics-server
# In a new dedicated terminal:
minikube tunnel

# 2. /etc/hosts (once per machine)
echo "127.0.0.1  youtube-manager.local" | sudo tee -a /etc/hosts

# 3. Build images into minikube
eval $(minikube docker-env)
docker build -t youtube-manager-backend:dev ./backend
docker build \
  --build-arg NEXT_PUBLIC_API_URL=http://youtube-manager.local/api/v1 \
  -t youtube-manager-frontend:dev ./frontend

# 4. Deploy via Helm (secrets.values.yaml must exist)
cp k8s/helm/youtube-manager/secrets.values.yaml.example \
   k8s/helm/youtube-manager/secrets.values.yaml
# edit secrets.values.yaml with real values
helm upgrade --install youtube-manager k8s/helm/youtube-manager/ \
  -f k8s/helm/youtube-manager/secrets.values.yaml \
  --rollback-on-failure --timeout 5m

# 5. Wait for everything to be ready
kubectl wait --for=condition=ready pod -l app=postgres --timeout=120s
kubectl wait --for=condition=ready pod -l app=redis --timeout=60s
kubectl wait --for=condition=available deployment/backend --timeout=180s
kubectl wait --for=condition=available deployment/frontend --timeout=120s

# 6. Verify
curl http://youtube-manager.local/api/v1/docs
open http://youtube-manager.local
```

## Day-to-Day Workflow (After Initial Setup)

```bash
# Terminal 1: always running
minikube tunnel

# Terminal 2: development
eval $(minikube docker-env)

# After changing backend code:
docker build -t youtube-manager-backend:dev ./backend
kubectl rollout restart deployment/backend
kubectl rollout status deployment/backend

# After changing frontend code:
docker build \
  --build-arg NEXT_PUBLIC_API_URL=http://youtube-manager.local/api/v1 \
  -t youtube-manager-frontend:dev ./frontend
kubectl rollout restart deployment/frontend

# After changing a manifest:
helm upgrade youtube-manager k8s/helm/youtube-manager/ \
  -f k8s/helm/youtube-manager/secrets.values.yaml

# After adding a migration:
# Just rebuild and restart — init container runs migrations on next pod start
docker build -t youtube-manager-backend:dev ./backend
kubectl rollout restart deployment/backend
```
