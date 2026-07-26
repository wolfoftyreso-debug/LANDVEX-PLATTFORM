# Kubernetes deployment (self-owned k3s)

The same single-deployable stack as compose, expressed as Kubernetes
manifests. Default target: the Terraform-provisioned node
(`infra/terraform`, `orchestrator = "k3s"`) running single-node k3s with
Traefik ingress and local-path storage on the DLM-snapshotted data volume.
The manifests are plain Kustomize — they apply to any conformant cluster
(including a shared org cluster) by swapping ingress class / storage class.

Section 3's "one deployable" principle is unchanged: Kubernetes is just the
orchestrator here, not an architecture change. Postgres and MinIO run
self-managed in-cluster, mirroring docker-compose.selfhost.yml.

## Layout

```
base/                 namespace, postgres, minio (+bucket init), migrate job,
                      app deployment, traefik ingress
overlays/prod/        patch real hostnames onto the ingress
optional/             cert-manager ClusterIssuer (Let's Encrypt)
base/secrets.example.yaml   template — real secret comes from .env.selfhost
```

## Deploy (on the k3s node)

```sh
# 1. Build both images locally and import into k3s containerd
docker build -t baltic-bridge:local --target runner .
docker build -t baltic-bridge-migrate:local --target build .
docker save baltic-bridge:local baltic-bridge-migrate:local | \
  sudo k3s ctr images import -

# 2. Secrets: one Secret from the same env file the compose stack uses
sudo k3s kubectl create namespace baltic-bridge --dry-run=client -o yaml | sudo k3s kubectl apply -f -
sudo k3s kubectl -n baltic-bridge create secret generic baltic-bridge-env \
  --from-env-file=.env.selfhost

# 3. Edit overlays/prod/kustomization.yaml (real hostnames), then:
sudo k3s kubectl apply -k infra/k8s/overlays/prod

# 4. First boot only — seed:
sudo k3s kubectl -n baltic-bridge run seed --rm -it --restart=Never \
  --image=baltic-bridge-migrate:local --overrides='{"spec":{"containers":[{"name":"seed","image":"baltic-bridge-migrate:local","command":["npm","run","db:seed"],"envFrom":[{"secretRef":{"name":"baltic-bridge-env"}}]}]}}'
```

Releases: rebuild + reimport the images, delete and re-apply the `migrate`
Job (append-only migrations run before the new app rolls), then
`kubectl -n baltic-bridge rollout restart deployment/app`.

## TLS

Install cert-manager and apply `optional/cert-manager-issuer.yaml`
(Let's Encrypt — the one deliberate external call), or create the
`app-tls`/`files-tls` secrets from your own CA and remove the
cert-manager annotation from the Ingress.

## Notes

- `S3_ENDPOINT` must be the PUBLIC files hostname routed by the ingress to
  minio:9000 — presigned URL signatures include the host.
- `replicas: 1` on the app is stage discipline, not a constraint — pg-boss
  coordinates via Postgres locks, so scaling out is safe later.
- Backups are orchestrator-aware: the Terraform cron detects k3s and runs
  `pg_dump` via kubectl exec; DLM snapshots the volume that holds the PVCs.
- Multi-node/HA (external etcd, replicated storage) is deliberately out of
  Phase 0–1 scope — revisit when load justifies it.
