# Why I Migrated a Production App from Supabase + Vercel to GKE (And What It Actually Cost)

I shipped a side project eight months ago on the stack you're "supposed to" use in 2026: Next.js on Vercel, FastAPI serverless via the Vercel Python runtime, Supabase Postgres, Upstash Redis. Connecting these services was a single environment variable. Deploy was `git push`. Auth worked in an afternoon. I was productive and it was boring in exactly the way everyone promises.

Then I ripped it all out and rebuilt it on a GKE cluster running Helm-managed workloads.

This isn't a "serverless doesn't scale" post. Serverless scales fine. This is about what serverless stops you from understanding, what standing up your own infrastructure teaches you that reading k8s.guru never will, and why sometimes the right engineering decision is the one with worse economics.

I'm going to walk through the full arc — the original architecture, what broke, the replacements, the things Theory didn't prepare me for, and a clear-eyed accounting of the tradeoffs. Every number here is real. Every issue actually happened.

---

## The Original Stack

The YouTube Manager AI app lets users authenticate with their Google account, import liked YouTube videos, and auto-categorize them with OpenAI. Standard three-tier webapp.

**Frontend:** Next.js 16 (App Router) on Vercel Pro  
**Backend:** FastAPI, deployed as a Vercel serverless function through `vercel.json` + `index.py`  
**Database:** Supabase managed Postgres (connection pooling via PgBouncer)  
**Cache/Queue:** Upstash Redis  
**CI/CD:** Vercel auto-deploy on push to `main`  
**Auth:** JWT tokens (30min access, 7-day refresh) stored in Redis  
**SSE:** Server-Sent Events for real-time sync progress streaming

This worked. The app was stable. Users could log in, sync thousands of videos, get AI-generated tags. Here's what it looked like:

```
Browser ──► Vercel CDN ──► Next.js (serverless)
                              └── FastAPI (serverless via index.py)
                                    └── Supabase (managed Postgres)
                                    └── Upstash (managed Redis)
```

Each `git push main` triggered a Vercel deploy that ran `npm run build` in 90 seconds and swapped the deployment atomically. Zero-ops. I didn't think about TLS certificates or node pools or ingress controllers. I thought about features.

---

## What Broke, In Order

### 1. Cold Starts Are Real and They're Embarrassing

After idle periods (Vercel scales serverless functions to zero), the first API request took 4-8 seconds. FastAPI imports all of SQLAlchemy, pydantic-settings, and the OpenAI client. The Vercel Python runtime cold-boots the entire process per-request for a user who hasn't interacted in 30 minutes.

Serverless advocates say "this is fine, just add a cron job." That is an admission that the model doesn't fit the workload. A cron job that pings `/health` every 5 minutes to keep functions warm is a workaround for a pricing model, not an engineering solution.

### 2. Long-Running Tasks Don't Fit the 10-Second Ceiling

The YouTube sync job fetches a user's liked videos via the YouTube Data API v3, paginates, and calls OpenAI for each batch of 10 videos. At 500+ liked videos — which is normal for an active YouTube user — this takes 90-180 seconds. Vercel's free tier has a 10-second function timeout. Even on Pro, you get 60 seconds. The API can't handle the actual workload without externalizing it to a queue (QStash), which adds cost, complexity, and a whole new failure domain.

### 3. SSE Streaming Is Hostile to Serverless

SSE requires a persistent HTTP connection. Serverless platforms close connections aggressively. I needed `nginx.ingress.kubernetes.io/proxy-read-timeout: "300"` on every SSE route, and Vercel doesn't give you that knob. The progress stream would die silently at 60 seconds, and the frontend had no way to know the sync was still running on the backend.

### 4. Supabase Limitations Became Structural

Supabase is excellent for getting started. The pain emerges later:

- **Migration workflow is two-headed**: You maintain Alembic migrations in the backend repo AND generate Supabase CLI migration SQL files from them. When the Alembic history diverges from `supabase_migrations.schema_migrations` (which it did, twice), you're deep in undocumented territory manually reconciling revision hashes.
- **Connection pooling is a black box**: Supabase uses PgBouncer, but you can't tune it. A sync job opening 50 connections to batch-insert videos would get throttled with no visibility into why.
- **pgvector isn't first-class**: The app needs `pgvector` for AI embeddings. Supabase supports it, but getting the right version with the right index types required support tickets.

### 5. Observability Was a Spreadsheet of Tabs

To understand why an API call was slow, I needed:
- Vercel function logs (one tab)
- Supabase query insights (another tab)
- Upstash Redis metrics (a third tab)
- Google Cloud Console for the YouTube Data API quota (fourth tab)

No unified log stream. No distributed tracing. No `kubectl logs -l app=backend --tail=200` to see everything in one terminal.

### 6. Vendor Lock-In Is Cumulative

Every managed-service integration creates a dependency that isn't visible until you try to leave. The app's auth flow was tied to Supabase's `auth.users` table. The Redis caching layer used Upstash-specific REST endpoints (not native Redis protocol). The deployment pipeline was `vercel build` — not transferable to any other platform.

---

## Why GKE, Specifically

The straightforward choice for "I want to learn Kubernetes in production" is EKS. You already have an AWS account. The documentation is better. The ecosystem around IAM roles and ALB ingress is more mature.

I picked GKE for two reasons:

1. **$300 trial credit**. Google Cloud gives new signups $300 in credits. A single e2-medium node pool in `us-central1` costs about $25/month. The trial effectively covered the entire learning period.

2. **GKE is genuinely the best managed Kubernetes**. It provisions faster than EKS, upgrades are automatic, and the control plane is free. AKS wasn't in consideration because this wasn't a corporate decision — it was a personal one.

If you don't have credits pushing you toward GCP, EKS is a perfectly fine choice. The specific cloud matters less than you think once you're past the node provisioning step.

---

## Architecture: The New Stack

```
Browser
  └── Google Cloud Load Balancer (TLS terminated at edge)
        └── GKE Gateway (gke-l7-global-external-managed)
              ├── /api/*  ──► backend-svc (ClusterIP) ──► FastAPI pods (1–5 replicas, HPA)
              ├── /mcp/*  ──► backend-svc
              └── /*      ──► frontend-svc (ClusterIP) ──► Next.js pods (1 replica)
                                                              │
                                              Pods share cluster DNS:
                                                ├── postgres-0.postgres:5432 (StatefulSet)
                                                └── redis-0.redis:6379 (StatefulSet)
```

**Every piece is self-hosted:**

| Component | Before (Managed) | After (Self-Hosted) |
|-----------|-----------------|---------------------|
| Postgres | Supabase | StatefulSet + pgvector image, PVC-backed |
| Redis | Upstash | StatefulSet, AOF persistence |
| Backend | Vercel serverless | Deployment + HPA, 1–5 replicas |
| Frontend | Vercel CDN | Deployment, 1 replica |
| TLS | Vercel-provisioned | cert-manager + Let's Encrypt ClusterIssuer |
| Ingress | Vercel routing | GKE Gateway controller |
| CI/CD | Vercel auto-deploy | GitHub Actions (lint/typecheck/test) + `deploy.sh` (build/push/helm) |
| Migration | Two-headed (Alembic + Supabase CLI) | Alembic-only via init container |
| Monitoring | Five disparate dashboards | `kubectl` + `kubetail` + stdout logs |

---

## Helm Chart Design

The chart lives at `k8s/helm/youtube-manager/`. Fourteen templates, one `values.yaml` for local (minikube), one `gcp.values.yaml` for production.

**Template structure:**

```
templates/
  _helpers.tpl              — shared labels, DATABASE_URL construction
  configmap.yaml            — non-sensitive config (CORS origins, model name, Redis URL)
  secret.yaml               — passwords, API keys (decoupled from chart, passed at deploy)
  backend/
    deployment.yaml         — init container (alembic upgrade head) + main container
    service.yaml            — ClusterIP:8000
    hpa.yaml                — CPU 70% / memory 150% triggers
  frontend/
    deployment.yaml         — simplest manifest: no env injection needed
    service.yaml            — ClusterIP:3000
  postgres/
    statefulset.yaml        — pgvector/pgvector:pg15, PGDATA subdirectory to avoid lost+found
    pvc.yaml                — 5Gi, ReadWriteOnce
    service.yaml            — headless (clusterIP: None)
  redis/
    statefulset.yaml        — redis:7-alpine, --appendonly yes
    pvc.yaml                — 1Gi
    service.yaml            — headless
  ingress/
    ingress.yaml            — TLS via cert-manager annotation
```

**Design decisions worth calling out:**

- **Init container for migrations.** The backend Deployment runs `alembic upgrade head` in an init container before the main uvicorn process starts. If the migration fails, the pod never enters Ready state, and traffic is never routed to a schema-mismatched backend. When scaling to 3 replicas, all 3 init containers run concurrent migrations — PostgreSQL's advisory lock handles serialization, only one actually runs, the others exit successfully.

- **Headless Services for databases.** Regular ClusterIP Services round-robin across pods. For StatefulSets, you need a specific pod (`postgres-0`), not any pod. A headless service (`clusterIP: None`) returns the pod IP directly via DNS.

- **`DATABASE_URL` constructed via env var substitution.** The PostgreSQL password lives in a Kubernetes Secret. `DATABASE_URL` should not be a Secret (the hostname isn't secret) and should not be a ConfigMap (the password is). It's constructed in the Deployment spec using `$(POSTGRES_PASSWORD)` substitution — the K8s-native way to compose a connection string from mixed-sensitivity parts.

- **Build-time vs. runtime env vars in Next.js.** `NEXT_PUBLIC_*` variables are inlined into the JavaScript bundle at `npm run build` time. They cannot be changed at runtime. The frontend Deployment has zero `env` or `envFrom` blocks — that's not a bug, it's a constraint of Next.js's architecture. Every API URL change requires rebuilding and re-pushing the frontend Docker image.

---

## The Migration: What Actually Happened

### Phase 1: minikube (Local)

Before touching GCP, I built everything on minikube. This was the right call — 10 of the 10 GKE issues I later hit were things I could have debugged locally, but some (like the VPA conflict and firewall rules) only manifest on a managed cloud cluster.

The local cluster taught me:
- `minikube tunnel` is required on macOS to route LoadBalancer traffic to `127.0.0.1`
- `eval $(minikube docker-env)` redirects `docker build` into minikube's daemon — images go directly onto the node
- `imagePullPolicy: Never` is mandatory when using local images; default is `IfNotPresent`, which tries Docker Hub and fails

### Phase 2: GKE (Cloud)

This phase generated the bulk of the documented issues. Here are the ones that cost the most time:

**Issue 1 — ARM64 images on AMD64 nodes.** I'm on an Apple Silicon Mac. `docker build` produces ARM64 images by default. GKE nodes run AMD64. The error is `exec format error` — a binary incompatibility that gives zero context. Fixed with `docker buildx build --platform linux/amd64 --push`.

**Issue 2 — Artifact Registry region mismatch.** Created the registry in `asia-southeast1`. The GKE cluster is in `us-central1`. Cross-region image pulls fail with opaque `PERMISSION_DENIED` errors. Had to recreate the registry in `us-central1` and re-push all images. Lesson: always colocate your image registry with your cluster.

**Issue 3 — Static IP type.** Reserved a global static IP. GKE LoadBalancer Services require regional IPs. The global IP address silently doesn't work — the service shows `EXTERNAL-IP: <pending>` for hours with no error event. Changed to a regional IP in `us-central1`. This cost me 3 hours because GCP's error messaging for this mismatch is nonexistent.

**Issue 4 — TLS cert-manager HTTP-01 firewall block.** GKE doesn't automatically create a firewall rule for port 80. cert-manager's HTTP-01 challenge to Let's Encrypt timed out with a `connection: Timeout` error. I had to manually create `gcloud compute firewall-rules create allow-http-https-lb --allow tcp:80,tcp:443 --source-ranges=0.0.0.0/0`. This is documented in GKE's ingress docs but buried in a paragraph about "manual configuration."

**Issue 5 — TrustedHostMiddleware rejects kubelet probes.** The backend has `TrustedHostMiddleware` that only allows requests from the configured CORS origin (e.g., `34-133-199-84.nip.io`). Kubernetes kubelet sends readiness/liveness probes to the pod IP with `Host: <pod-ip>`. Middleware rejects these as untrusted, returning 400. Fixed by adding `httpHeaders: [{name: Host, value: {{ .Values.domain }}}]` to the probe definitions.

**Issue 6 — `postgres` CrashLoopBackOff.** GKE PVCs are ext4-formatted, which creates a `lost+found` directory at the mount root. PostgreSQL refuses to initialize if its data directory is non-empty. Fixed by setting `PGDATA=/var/lib/postgresql/data/pgdata` to use a subdirectory.

**Issue 7 — VPA recommender conflict.** GKE's Vertical Pod Autoscaler recommender took field manager ownership of `.spec.replicas` on the backend Deployment. Subsequent `helm upgrade` commands failed with `conflict with "vpa-recommender"`. Fix: `kubectl delete deployment backend` to release ownership, then re-run `helm upgrade`.

---

## CI/CD Shift: From Push-to-Deploy to Pipeline

Vercel's deployment model is `git push main` → deployed. That's genuinely hard to replace. My replacement:

1. **GitHub Actions** (`.github/workflows/`) handles linting (Black, Ruff, MyPy for backend; Biome, TypeScript for frontend), type checking, and test suites with coverage reports uploaded to Codecov.

2. **`deploy.sh`** handles the actual deployment. It's a 180-line script that:
   - Reads the current image tag from `gcp.values.yaml`
   - Bumps the version number (`v5` → `v6`)
   - Builds the Docker image with `--platform linux/amd64`
   - Pushes to Artifact Registry
   - Updates `gcp.values.yaml` with the new tag
   - Runs `helm upgrade --install`
   - Watches pod status for 60 seconds

The script is deliberately not a GitHub Actions workflow. CI runs on every PR, deploy is a manual `./deploy.sh backend` from my terminal. This is intentional — I want the gate of manual verification before hitting production, and I don't want a green CI badge coupled to a production mutation.

The copy is `cp k8s/helm/youtube-manager/secrets.values.yaml.example secrets.values.yaml`, edit with real values, and the file is gitignored. No secrets in version control.

---

## What Theory Didn't Prepare Me For

I read *Kubernetes in Action*. I did the Katacoda scenarios. I understood Deployments, Services, Ingresses, PVCs, and Helm templates conceptually. Here's what the books didn't cover:

### The `lost+found` Problem

When you read about Kubernetes on a Mac, your PVCs are backed by `hostPath` on a Docker Desktop VM. They're clean directories. In production, your PVC is an ext4-formatted persistent disk provisioned by a cloud storage class. ext4 creates a `lost+found` directory at the filesystem root. PostgreSQL's init process checks if the data directory is empty — it isn't — and refuses to start. This is documented nowhere in the PostgreSQL-on-Kubernetes ecosystem in a way you'd find before hitting it.

### The Architecture Segmentation Fault

`docker build` on Apple Silicon produces ARM64 binaries. `docker buildx build --platform linux/amd64` works, but it uses QEMU emulation during the build, which is slow (3-5x slower than native builds). I didn't think about CPU architecture as a deployment concern because serverless platforms abstract it away. Running your own nodes makes every `docker build` a cross-compilation step.

### cert-manager Is a Rube Goldberg Machine

cert-manager works beautifully when it works. When it doesn't, the debugging chain is: Let's Encrypt ACME API → cert-manager controller → Kubernetes Certificate resource → Kubernetes Secret → GKE Gateway → GCP Load Balancer → firewall rule → the actual port 80 listener on the node. Any one of these breaks silently, and the error messages are propagated through different layers with different formats. The `cert-manager.io/issue-temporary-certificate: "true"` annotation was the fix for a chicken-and-egg problem where the Gateway refuses to route until a TLS secret exists, but cert-manager can't get the secret until the Gateway routes HTTP-01 challenge traffic.

### VPA Takes Ownership of Your Replicas

GKE installs a Vertical Pod Autoscaler recommender by default. It takes Kubernetes field manager ownership of fields it manages. When Helm tries to declaratively manage `.spec.replicas` and VPA also manages it, you get a field ownership conflict. The only fix is to delete the resource and let Helm recreate it. This is GKE-specific behavior not covered in general Kubernetes documentation.

---

## Honest Tradeoffs

### What Got Better

**Cold starts: gone.** Pods are always running. A restart takes 8 seconds (container start + alembic init + uvicorn workers), and it only happens on deploy or pod failure. User experience is consistent regardless of idle time.

**Long-running tasks work natively.** The 90-180 second sync job runs as a regular HTTP request with a 300-second proxy timeout. No need for external queues or background workers. SSE streams stay open.

**Observability is centralized.** `kubectl logs -l app=backend --tail=200 --follow` shows everything. Adding `kubetail` gives color-coded multi-pod log streaming. Database logs, Redis logs, backend logs, and ingress logs all flow through `kubectl`. I can correlate a slow request across the entire stack in a single terminal.

**Database migration is now one system.** Alembic runs in an init container. No more synchronizing `supabase_migrations.schema_migrations` with `alembic_version`. Migrations are immutable in the Docker image — the same image runs in minikube, GKE, and any future environment.

**Portability is real.** The entire application — database, cache, backend, frontend, ingress rules, TLS provisioning — is defined in a single Helm chart with environment-override values files. I can spin up the full stack on minikube in 10 minutes with one `helm install` command.

**I actually understand my infrastructure.** When something breaks, there's no support ticket to file and no dashboard to check. The error is in `kubectl describe pod` or `kubectl logs`. The fix is in the Helm template or the Dockerfile. This is a skill investment, not just an infrastructure investment.

### What Got Worse

**Compute costs are permanently higher.** A single e2-medium node in GKE costs $24.54/month, always-on. Add the static IP ($7.30/month if not attached to a load balancer), the persistent disks for Postgres and Redis (~$3/month for 6Gi total), and Artifact Registry storage (~$1/month). Total: approximately **$36/month**.

The Vercel Pro + Supabase Pro + Upstash combination was roughly **$45/month**, but it scaled with usage — at zero traffic, functions cost nothing. On GKE, the cluster costs $24.54/month regardless of whether anyone is using the app.

For a project this size, the cost is negligible either way. But if you're running five side projects on Vercel's free tier, the GKE approach becomes expensive fast.

**Operational burden is mine alone.** I now maintain:
- GKE node version upgrades (automatic but must be monitored)
- cert-manager certificate renewals (automatic for 90 days, but needs to be verified)
- Postgres backups (not yet implemented — currently accepting the risk of PVC loss)
- Docker image registry cleanup
- Helm chart version management
- SSH keys and Artifact Registry authentication

None of this existed in the serverless model. The Vercel/Supabase stack had approximately zero operational overhead. The GKE stack has nonzero operational overhead.

**The developer experience isn't as smooth as `git push`.** The deploy.sh script replaces `git push` with `./deploy.sh backend` followed by waiting 3-5 minutes for the image build, push, and Helm upgrade to complete. With Vercel, I pushed code and forgot about it. With GKE, I'm actively involved in every deployment.

Local development still works (uvicorn --reload and npm run dev), so the dev loop is unchanged. It's the production deploy loop that's heavier.

**Single node = single point of failure.** The cluster runs on one e2-medium node. If that node dies, everything is unreachable until GKE replaces it (typically 5-10 minutes) and the pods reschedule. A multi-node setup would fix this but doubles the cost. For a learning project, this is an acceptable tradeoff. For a business, it wouldn't be.

---

## Who Should Do This

**Do this migration if:**

- You've learned Kubernetes from books and courses and the gap between knowing the primitives and operating a real cluster is bothering you.
- Your workload doesn't fit the serverless model (long-running tasks, persistent connections, SSE/WebSockets) and you're building workarounds instead of features.
- You want observability that doesn't require switching between three different vendor dashboards.
- You're willing to accept higher baseline costs and nonzero operational burden in exchange for portable infrastructure and deep technical understanding.

**Don't do this migration if:**

- Your app fits neatly within serverless constraints (sub-10s responses, stateless, no persistent connections).
- You have multiple side projects and the operational overhead would multiply rather than consolidate.
- Your primary goal is to ship features quickly and infrastructure is a distraction, not an interest.
- You're building a business where uptime matters and you don't have time to learn what a VPA conflict is at 2 AM.

---

## What I'd Do Differently

**Use Cloud SQL instead of in-cluster Postgres.** The Postgres StatefulSet works, but I have no automated backups, no connection pooling beyond what SQLAlchemy provides, and no disaster recovery story. Cloud SQL provides all of this with a single Terraform resource. The StatefulSet was a learning exercise; for anything resembling production, move the database to a managed service and keep the stateless workloads on Kubernetes.

**Use Memorystore instead of in-cluster Redis.** Same reasoning. The Redis StatefulSet has AOF persistence but no replication, no failover, and no monitoring beyond `redis-cli INFO`.

**Start with GKE Gateway, not ingress-nginx.** I installed ingress-nginx initially, discovered it doesn't integrate with GCP Load Balancers, then switched to the native GKE Gateway controller. Starting with the Gateway from day one would have saved the migration effort between ingress controllers and the associated TLS reconfiguration.

**Add Terraform.** The cluster, static IP, Artifact Registry, firewall rules, and service accounts are all created manually via `gcloud` CLI commands. Terraform would make these reproducible and auditable. The Helm chart handles application resources; Terraform should handle cloud resources.

**Add monitoring.** Prometheus + Grafana on the cluster, or GCP Cloud Monitoring, would replace `kubectl top pods` with actual dashboards. Right now I'm operating at the CLI level, which works for one person but doesn't scale.

---

## Final Numbers

| | Before (Vercel + Supabase) | After (GKE) |
|---|---|---|
| Cold start latency | 4–8 seconds | 0 (always-on) |
| Max task duration | 60 seconds (Vercel Pro) | 300 seconds (configurable) |
| Monthly compute cost | $45 (Pro plans, scales with usage) | $36 (flat, always-on) |
| Deployment time | 90 seconds (Vercel build) | 3–5 minutes (build + push + helm) |
| Observability surfaces | 5 separate dashboards | 1 terminal |
| Operational ownership | 0 hours/month | 1–2 hours/month |
| Portability | Vercel-locked | Any Kubernetes cluster |
| TLS management | Automatic (Vercel) | cert-manager + Let's Encrypt |
| DB migration workflow | Two systems (Alembic + Supabase CLI) | One system (Alembic init container) |
| Dependencies | 3 managed services | 1 cloud provider, 0 managed services |
| Learning tax | $0 (theory only) | ~10 hours of debugging across 7 documented issues |

The migration took roughly 40 hours spread across two weeks — about half of which was debugging the 10 documented issues in the GKE deployment report. If I were doing it again with what I now know, it'd take about 6 hours.

The single biggest thing I learned: Kubernetes theory teaches you the API objects. Operating a cluster teaches you that every cloud provider silently diverges from the spec in ways that only surface at 11 PM when a pod won't schedule and the event log says `field is immutable` with no other context.

I'd do it again. Not because it saved money (it didn't) or because it made the app faster (cold starts were the only real performance issue). I'd do it again because I can now read any Kubernetes manifest, on any cloud, and understand what it's doing at the pod level, the network level, and the storage level. That knowledge compounds across every project I'll work on for the rest of my career.

---

*The infrastructure code for this migration lives at [k8s/helm/youtube-manager/](/k8s/helm/youtube-manager/). The full deployment report — including every error, fix, and shell command — is in [docs/gke-deployment-report.md](/docs/gke-deployment-report.md).*
