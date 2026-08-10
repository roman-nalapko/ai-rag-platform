# Backlog Process

This project uses a lightweight portfolio-friendly backlog. The goal is to make
the next engineering step obvious without turning the repository into project
management theater.

## Source of truth

- `BACKLOG.md` is the canonical backlog.
- GitHub Issues can mirror backlog items when work becomes active.
- README should only link to the backlog and show the high-level roadmap.

## Labels

Recommended GitHub labels:

| Label | Use |
| --- | --- |
| `area:api` | FastAPI routes, request/response contracts |
| `area:db` | PostgreSQL, SQLAlchemy, Alembic |
| `area:rag` | Chunking, embeddings, Qdrant, retrieval |
| `area:llm` | LM Studio and provider abstraction |
| `area:infra` | Docker, CI, deployment, workers |
| `area:tests` | Unit, contract, integration, evaluation tests |
| `area:docs` | README, guides, examples |
| `priority:p0` | Broken core flow or security issue |
| `priority:p1` | Strong production/recruiter value |
| `priority:p2` | Useful but not urgent |
| `priority:p3` | Nice-to-have |
| `status:ready` | Clear and ready to implement |
| `status:blocked` | Needs a decision or external dependency |

## Milestones

### MVP

Already complete. Represents the public portfolio baseline.

### V1 - production hardening

Focus:

- integration tests;
- durable background jobs;
- authentication and tenant enforcement;
- document lifecycle;
- better operational readiness.

### V2 - retrieval quality and platform expansion

Focus:

- reranking;
- hybrid retrieval;
- richer evaluation;
- provider abstraction;
- demo UI;
- deployment profiles.

## Working rule

Each implementation task should fit in one small PR/commit and answer:

1. What problem does it solve?
2. What files or modules are in scope?
3. How do we verify it?
4. What is explicitly out of scope?

If the answer is not clear, keep the item in `Backlog` instead of starting it.

## Definition of done

A task is done only when:

- implementation is complete;
- tests/checks were run in proportion to risk;
- docs or examples are updated if behavior changed;
- no secrets or local artifacts are staged;
- README/backlog state still matches the code.
