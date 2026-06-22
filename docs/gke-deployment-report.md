# GKE Deployment Report — YouTube Manager AI

## Overview

This document captures every issue encountered and fix applied while deploying YouTube Manager AI to Google Kubernetes Engine (GKE) on a $300 trial account.

**Final URL:** `https://34-133-199-84.nip.io`  
**Cluster region:** `us-central1`  
**Artifact Registry:** `us-central1-docker.pkg.dev/project-e89d58ee-f2c4-41bd-a30/youtube-manager`

---

## Infrastructure Provisioned

| Component | Details |
|---|---|
| GKE Cluster | `us-central1`, single node pool (e2-medium) |
| Artifact Registry | `us-central1`, repository: `youtube-manager` |
| Static IP | `34.133.199.84`, regional (`us-central1`) |
| ingress-nginx | Installed via Helm, LoadBalancer type |
| cert-manager | Installed via Helm, ClusterIssuer: `letsencrypt-prod` |
| Helm chart | `k8s/helm/youtube-manager/` — custom chart for all app resources |

---

## Issues Encountered & Fixes Applied

### 1. PostgreSQL CrashLoopBackOff — `lost+found` directory

**Symptom:**
```
postgres-0   0/1   CrashLoopBackOff
```
**Cause:** GKE PVCs are formatted with ext4, which creates a `lost+found` directory at the mount root. Postgres refuses to initialize if the data directory is non-empty.

**Fix:** Added `PGDATA` env var to the StatefulSet template to use a subdirectory:
```yaml
# k8s/helm/youtube-manager/templates/postgres/statefulset.yaml
- name: PGDATA
  value: /var/lib/postgresql/data/pgdata
```
Had to force-delete the `postgres-0` pod after applying so it picked up the new env var.

---

### 2. `exec format error` — ARM64 images on AMD64 GKE nodes

**Symptom:**
```
exec /usr/local/bin/python: exec format error
```
**Cause:** Images built on Apple Silicon (ARM64 / M-series Mac) are ARM64 by default. GKE nodes run AMD64 (x86_64). The wrong architecture binary cannot execute.

**Fix:** Use `docker buildx` with explicit platform targeting:
```bash
docker buildx build --platform linux/amd64 --push \
  -t <registry>/backend:v3 ./backend
docker buildx build --platform linux/amd64 --push \
  --build-arg NEXT_PUBLIC_API_URL=https://34-133-199-84.nip.io/api/v1 \
  -t <registry>/frontend:v3 ./frontend
```
Used `desktop-linux` builder (Docker Desktop) which supports `linux/amd64` via QEMU emulation on Apple Silicon.

---

### 3. Node cached old ARM64 image despite new push

**Symptom:** Even after rebuilding with `--platform linux/amd64`, nodes served the old ARM64 image.

**Cause:** `imagePullPolicy: IfNotPresent` — nodes served the locally cached ARM64 image instead of pulling from registry.

**Fix:**
- Changed `pullPolicy` to `Always` in `gcp.values.yaml` for both backend and frontend
- Bumped image tag (v1 → v2 → v3) to guarantee a fresh pull with no cache ambiguity

---

### 4. Artifact Registry — region mismatch

**Symptom:** `PERMISSION_DENIED` / image pull failures on GKE nodes.

**Cause:** Artifact Registry repository was initially created in `asia-southeast1`, but the GKE cluster is in `us-central1`. Nodes in `us-central1` couldn't pull across regions without correct repository URL configuration.

**Fix:** Created a new Artifact Registry repository in `us-central1`, re-tagged and re-pushed all images to the correct regional URL:
```
us-central1-docker.pkg.dev/project-e89d58ee-f2c4-41bd-a30/youtube-manager/backend:v3
us-central1-docker.pkg.dev/project-e89d58ee-f2c4-41bd-a30/youtube-manager/frontend:v3
```
Updated `gcp.values.yaml` with the new repository URLs.

---

### 5. ConfigMap missing `ALGORITHM` and `OPENAI_MODEL`

**Symptom:** Backend started but config values were empty strings.

**Cause:** `gcp.values.yaml` didn't override `config.algorithm` and `config.openaiModel`, and the ConfigMap template had no `| default` fallback for those keys.

**Fix:**
- Added `| default` fallbacks in `templates/configmap.yaml`:
```yaml
ALGORITHM: {{ .Values.config.algorithm | default "HS256" | quote }}
OPENAI_MODEL: {{ .Values.config.openaiModel | default "gpt-5.2" | quote }}
```
- Added explicit values in `gcp.values.yaml`:
```yaml
config:
  algorithm: "HS256"
  openaiModel: "gpt-5.2"
```

---

### 6. ingress-nginx LoadBalancer `EXTERNAL-IP: <pending>` for 3+ hours

**Symptom:** `kubectl get svc ingress-nginx-controller` showed `EXTERNAL-IP: <pending>` indefinitely.

**Root cause (attempt 1):** The reserved static IP `34.160.145.250` was a **global** IP. GKE LoadBalancer services require a **regional** IP. Patching the service with a global IP is silently ignored.

**Fix:** Created a **regional** static IP in `us-central1`:
```bash
gcloud compute addresses create youtube-manager-regional --region=us-central1
```
Got the new IP `34.133.199.84`, patched the service, and updated all domain references in `gcp.values.yaml` from `34-160-145-250.nip.io` to `34-133-199-84.nip.io`.

---

### 7. TLS cert-manager HTTP-01 challenge — firewall blocked

**Symptom:**
```
400 urn:ietf:params:acme:error:connection: Timeout during connect (likely firewall problem)
```
**Cause:** GKE did not automatically create a firewall rule allowing inbound port 80 to the nodes. Let's Encrypt couldn't reach the ACME HTTP-01 challenge URL.

**Fix:** Manually created a GCP firewall rule:
```bash
gcloud compute firewall-rules create allow-http-https-lb \
  --allow tcp:80,tcp:443 \
  --network=default \
  --source-ranges=0.0.0.0/0
```
Then deleted the failed cert-manager order and certificate request to force a retry:
```bash
kubectl delete order youtube-manager-tls-1-2156761331
kubectl delete certificaterequest youtube-manager-tls-1
kubectl delete certificate youtube-manager-tls
```
Certificate issued successfully after retry.

---

### 8. Liveness probe returning HTTP 400 — `TrustedHostMiddleware`

**Symptom:**
```
Warning  Unhealthy  Liveness probe failed: HTTP probe failed with statuscode: 400
```
**Cause:** In production mode, `main.py` applies `TrustedHostMiddleware` which only allows requests from configured CORS origins (e.g., `34-133-199-84.nip.io`). Kubernetes liveness/readiness probes send HTTP requests directly to the pod IP with `Host: <pod-ip>`, which the middleware rejects with 400.

**Fix:** Added the domain as a `Host` header in the probe definitions in `templates/backend/deployment.yaml`:
```yaml
readinessProbe:
  httpGet:
    path: /health
    port: 8000
    httpHeaders:
      - name: Host
        value: {{ .Values.domain }}
livenessProbe:
  httpGet:
    path: /health
    port: 8000
    httpHeaders:
      - name: Host
        value: {{ .Values.domain }}
```
No image rebuild required — pure Helm template change.

---

### 9. Helm upgrade conflict with VPA recommender on `.spec.replicas`

**Symptom:**
```
conflict with "vpa-recommender" with subresource "scale" using apps/v1: .spec.replicas
Error: UPGRADE FAILED
```
**Cause:** GKE's Vertical Pod Autoscaler (VPA) recommender took field manager ownership of `.spec.replicas` on the backend Deployment, conflicting with Helm's apply.

**Fix:** Deleted the backend Deployment first to release the VPA ownership, then re-ran `helm upgrade`:
```bash
kubectl delete deployment backend
helm upgrade --install youtube-manager k8s/helm/youtube-manager/ \
  -f k8s/helm/youtube-manager/gcp.values.yaml \
  -f k8s/helm/youtube-manager/secrets.values.yaml
```

---

### 10. Frontend calling old IP — `NEXT_PUBLIC_API_URL` baked at build time

**Symptom:** Login XHR requests went to `https://34-160-145-250.nip.io/api/v1/auth/youtube/login` (old IP) instead of the new one.

**Cause:** `NEXT_PUBLIC_*` environment variables in Next.js are inlined at `npm run build` time, not at runtime. The frontend image v2 was built with the old IP baked in.

**Fix:** Rebuilt the frontend image with the correct `NEXT_PUBLIC_API_URL`:
```bash
docker buildx build --platform linux/amd64 --push \
  --build-arg NEXT_PUBLIC_API_URL=https://34-133-199-84.nip.io/api/v1 \
  -t <registry>/frontend:v3 ./frontend
```
Updated `gcp.values.yaml` frontend tag to `v3` and redeployed.

---

## Key Learnings

| Topic | Learning |
|---|---|
| **ARM64 → AMD64** | Always build with `--platform linux/amd64` when deploying to GKE from Apple Silicon |
| **Static IP type** | GKE LoadBalancer requires a **regional** static IP, not a global one |
| **PGDATA on GKE** | Always set `PGDATA` to a subdirectory — ext4 PVCs have `lost+found` at root |
| **Firewall rules** | GKE does not auto-open port 80 for ingress-nginx — must create firewall rule manually |
| **TrustedHostMiddleware** | K8s probes use pod IP as Host header — add `httpHeaders` to probes or whitelist `localhost` |
| **NEXT_PUBLIC_ vars** | These are build-time only — rebuilding the image is the only way to change them |
| **VPA conflict** | VPA can take ownership of `.spec.replicas` — delete the deployment to recover |
| **cert-manager retry** | After fixing the root cause, must manually delete failed order + certificaterequest to unblock |
| **imagePullPolicy** | Use `Always` in GCP to prevent stale cached images on nodes |

---

## Final State

```
NAME                                        READY   STATUS    RESTARTS
backend-69f6784b7c-vp9vv                    1/1     Running   0
frontend-xxx                                1/1     Running   0
ingress-nginx-controller-xxx                1/1     Running   0
postgres-0                                  1/1     Running   0
redis-0                                     1/1     Running   0
```

**App:** `https://34-133-199-84.nip.io`  
**TLS:** Valid Let's Encrypt certificate  
**Backend health:** `https://34-133-199-84.nip.io/api/v1/health` → `{"status":"healthy","database":"connected","redis":"connected"}`
