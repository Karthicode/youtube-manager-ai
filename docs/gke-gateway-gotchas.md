# GKE Gateway API & Cert-Manager: Lessons Learned & Gotchas

When migrating from standard Nginx Ingress to the native Google Cloud Gateway API (`gke-l7-global-external-managed`), several subtle infrastructure quirks can break your deployment. Here are the key gotchas to watch out for:

## 1. The Gateway TLS Chicken-and-Egg Problem
**The Issue:** 
When configuring HTTPS, your `Gateway` resource references a Kubernetes TLS secret (e.g., `youtube-manager-tls`). If this secret does not exist yet (because Cert-Manager is still trying to get it), GKE panics, marks the Gateway as "failed to translate," and refuses to update the load balancer routing. Because the load balancer isn't routing, Cert-Manager's HTTP-01 challenge traffic never reaches the cluster, meaning the certificate is never issued.
**The Fix:**
Always add the `cert-manager.io/issue-temporary-certificate: "true"` annotation to your `Certificate` resource. This forces Cert-Manager to instantly generate a self-signed dummy certificate to satisfy GKE, which unblocks the load balancer routing, allows the HTTP-01 challenge to pass, and automatically overwrites the dummy cert with the real Let's Encrypt certificate.

## 2. Google Cloud Health Checks vs. Backend Host Middleware
**The Issue:** 
Nginx Ingress relies on local Kubernetes `kubelet` readiness probes, which strictly obey custom `httpHeaders` (like `Host: yourdomain.com`). However, GKE Gateway creates native **Google Cloud Load Balancer (GCLB) Health Checks**. GCLB often ignores custom `Host` headers and pings your backend pods directly via their internal IPs. If your backend (like FastAPI) uses `TrustedHostMiddleware`, it will reject these health checks with a `400 Bad Request`. GCLB will assume the pod is dead and return a `503 Service Unavailable` to the internet.
**The Fix:**
Disable `TrustedHostMiddleware` (or explicitly allow `*`) when running behind a GKE Gateway Load Balancer. The Gateway already drops external traffic that doesn't match your configured `Hostnames`, making the backend middleware redundant and actively harmful to GCP health checks.

## 3. Global SSL Propagation Delays & Browser Caching
**The Issue:** 
After Cert-Manager successfully acquires the Let's Encrypt certificate and reports `READY: True`, your browser might still show "Not Secure" and display the temporary dummy certificate.
**The Fix:**
Google Cloud Global Load Balancers take 10-15 minutes to propagate new SSL certificates across their global edge network. Additionally, web browsers aggressively cache TLS states. 
- Do not assume it's broken. 
- Use `curl -vI https://yourdomain.com` to bypass browser caching and inspect the raw edge certificate.
- Be patient, and test using an Incognito window or a different network (like your phone).

## 4. Next.js Build-Time Environment Variables
**The Issue:** 
If you change your infrastructure IP or domain name, updating `values.yaml` and running a Helm upgrade will fix the backend, but the frontend might still make requests to the old IP.
**The Fix:**
Next.js (and React) bake `NEXT_PUBLIC_` environment variables directly into the static Javascript bundle *during the Docker build process*. You must completely rebuild and re-push your frontend Docker image whenever your API domain/IP changes. Alternatively, use relative paths (e.g., `/api/v1/...`) instead of absolute URLs to make the frontend completely domain-agnostic.
