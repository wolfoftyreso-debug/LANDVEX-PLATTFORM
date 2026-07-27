# Documentation index

| Document | What |
|----------|------|
| [`dev-sync.md`](dev-sync.md) | **Start here.** Single entry point — coverage, API surface, integrations, pre-flight checklist, deployment, doc map. |
| [`architecture.md`](architecture.md) | Design decisions, data flow, roadmap. |
| [`aws.md`](aws.md) | **Deploying.** The AWS-native runbook: ECR → Fargate → ALB, Aurora, Secrets Manager, and the preflight gate the container runs before it serves. |
| [`DEPLOY.md`](DEPLOY.md) | The generic container/compose path. |
| [`aws-deployment.md`](aws-deployment.md) | The earlier EC2 + systemd handoff (port 8087, nginx). Still valid for that shape; `aws.md` supersedes it for Fargate. |
| [`production-readiness.md`](production-readiness.md) | Readiness status and remaining gaps. |
| [`openapi.json`](openapi.json) | Exported OpenAPI 3.0 specification. |
| [`history/`](history/) | Historical process artefacts (build-state prompts, review notes) — kept for provenance, not part of the current line. |

Project context for contributors lives in [`../CLAUDE.md`](../CLAUDE.md);
release notes in [`../CHANGELOG.md`](../CHANGELOG.md).
