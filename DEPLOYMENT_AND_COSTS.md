# MailMind v2: Deployment Architecture & Cost Analysis

## 1. TECH STACK

### Current (already in repo)

| Layer | Tech | Version | Purpose |
|---|---|---|---|
| **API** | FastAPI | 0.115+ | HTTP/REST, OpenAPI docs |
| **Agent Orchestration** | LangGraph | 0.2+ | DAG pipeline (ingest→triage→gate) |
| **LLM** | Azure OpenAI GPT-4o | 2024-12-01 | Triage, commitment, draft generation |
| **NLP** | spaCy + Presidio | 3.0+, 2.2+ | PII detection (names, locations, IDs) |
| **Server** | Uvicorn (ASGI) | 0.28+ | Async HTTP server |
| **Process Management** | Gunicorn | 23.0+ | Production WSGI/ASGI wrapper |
| **Frontend** | Next.js | 14+ | React SSR, API routes |
| **Observability** | Jaeger + Prometheus | (see docker-compose.yml) | Distributed tracing, metrics |
| **Containerization** | Docker | — | Container packaging |

### Required additions for queue/worker architecture

| Layer | Options | Recommendation | Cost |
|---|---|---|---|
| **Message Queue** | Redis, RabbitMQ, Azure Service Bus, AWS SQS | Redis (dev/staging), Azure SB (prod) | $15–200/mo |
| **Persistent DB** | PostgreSQL, Cosmos DB, Cloud SQL | PostgreSQL (self-hosted or RDS) | $50–500/mo |
| **Worker Runtime** | Kubernetes, Docker Compose, AWS Lambda, Azure Container Instances | K8s (prod), Docker Compose (dev) | $100–1000/mo |
| **Cache** | Redis | Redis (shared with queue) | included above |
| **Result Store** | PostgreSQL (same as above) | PostgreSQL | included above |

---

## 2. DEPLOYMENT ARCHITECTURES

### Development (local machine / docker-compose)

```
┌─────────────────────────────────────────────┐
│  DEVELOPMENT (docker-compose.yml)           │
├─────────────────────────────────────────────┤
│                                             │
│  Frontend (Next.js)                        │
│    :3000                                    │
│       ↓                                     │
│  Backend (FastAPI + LangGraph)             │
│    :8000                                    │
│    ├─ POST /api/agent/process (sync)       │
│    ├─ POST /api/agent/triage (fast)        │
│    └─ POST /api/agent/batch                │
│       ↓                                     │
│  Queue (in-memory deque)                   │
│    [EmailQueue in app/queue/queue.py]      │
│       ↓                                     │
│  [Single thread handles enqueued jobs]     │
│       ↓                                     │
│  Observability                             │
│    ├─ Jaeger (tracing)   :16686            │
│    └─ Prometheus         :9090             │
│                                             │
│  No external services needed               │
│                                             │
└─────────────────────────────────────────────┘

docker-compose up -d
→ Everything runs locally in ~5 containers
→ All code changes auto-reload (volumes)
```

**Cost:** $0 (runs on dev machine)

---

### Staging (cloud-lite, single region)

```
┌────────────────────────────────────────────────────────┐
│  STAGING (Azure / AWS)                                 │
├────────────────────────────────────────────────────────┤
│                                                        │
│  Load Balancer (Azure LB / AWS ALB)                   │
│    :443 (HTTPS)                                       │
│       ├─ Frontend (App Service / EC2)    × 2 replicas │
│       │    :3000                                       │
│       └─ Backend (App Service / EC2)     × 2 replicas │
│            :8000                                       │
│            ├─ POST /api/agent/triage (fast)           │
│            └─ Enqueue to Redis                        │
│                  ↓                                     │
│  Redis Cache + Queue                                  │
│    (Azure Cache for Redis / ElastiCache)              │
│       ↓                                                │
│  Worker Pool                                          │
│    ├─ Worker 1 (Docker container) × 3 replicas       │
│    ├─ Worker 2                                        │
│    └─ Worker 3                                        │
│       (commitment → calendar → rag → draft)           │
│          ↓                                             │
│  PostgreSQL (RDS / Azure Database)                    │
│    ├─ email_enrichment table                          │
│    ├─ audit_log                                       │
│    └─ user_tokens (Graph API refresh)                 │
│                                                        │
│  Monitoring                                           │
│    ├─ CloudWatch / Application Insights              │
│    ├─ Jaeger (managed or self-hosted)                │
│    └─ PagerDuty (alerting)                           │
│                                                        │
└────────────────────────────────────────────────────────┘

Terraform / CloudFormation:
  - App Service / EC2 (2 frontend, 2 backend replicas)
  - Azure Cache for Redis / ElastiCache (6GB)
  - Azure Database for PostgreSQL / RDS (B-class)
  - Load Balancer with health checks
  - Auto-scale policies (CPU >70%)
```

**Cost per month:**
```
Frontend (2× App Service Standard B1):        $37.26 × 2  = $74.52
Backend (2× App Service Standard B1):         $37.26 × 2  = $74.52
Redis (6GB, Basic tier):                      ~$15
PostgreSQL (B1MS, 100 DTUs):                  ~$150
Load Balancer:                                ~$20
Data transfer (egress):                       ~$30 (varies)
────────────────────────────────────────────────────
TOTAL INFRASTRUCTURE:                         ~$365/month
────────────────────────────────────────────────────
LLM API (GPT-4o): 10K emails/day, $0.015/triage, $0.02/draft
  = 10K × ($0.015 + $0.02) = $350/day = ~$10,500/month
────────────────────────────────────────────────────
TOTAL (staging):                              ~$10,865/month
```

---

### Production (enterprise-grade, multi-region, HA)

```
┌──────────────────────────────────────────────────────────┐
│  PRODUCTION (Kubernetes / Azure AKS)                     │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  [REGION: US-East]                [REGION: EU-West]     │
│  ┌───────────────────────┐  ┌────────────────────────┐ │
│  │ Load Balancer         │  │ Load Balancer          │ │
│  │   :443 (HTTPS)        │  │   :443 (HTTPS)         │ │
│  │   Geo-routing         │  │                        │ │
│  │   ↓                   │  │   ↓                    │ │
│  │ Kubernetes Cluster    │  │ Kubernetes Cluster     │ │
│  │ ┌─────────────────┐   │  │ ┌──────────────────┐   │ │
│  │ │ Frontend Pod    │   │  │ │ Frontend Pod     │   │ │
│  │ │ (3 replicas)    │×10│  │ │ (3 replicas)  ×5 │   │ │
│  │ │ Next.js         │   │  │ │ Next.js          │   │ │
│  │ └─────────────────┘   │  │ └──────────────────┘   │ │
│  │        ↓              │  │        ↓               │ │
│  │ ┌─────────────────┐   │  │ ┌──────────────────┐   │ │
│  │ │ Backend Pod     │   │  │ │ Backend Pod      │   │ │
│  │ │ (5 replicas)    │×10│  │ │ (5 replicas)  ×5 │   │ │
│  │ │ FastAPI + LG    │   │  │ │ FastAPI + LG     │   │ │
│  │ └─────────────────┘   │  │ └──────────────────┘   │ │
│  │        ↓              │  │        ↓               │ │
│  │ ┌─────────────────┐   │  │ ┌──────────────────┐   │ │
│  │ │ Worker Pod      │   │  │ │ Worker Pod       │   │ │
│  │ │ (10 replicas)   │×10│  │ │ (10 replicas) ×5 │   │ │
│  │ └─────────────────┘   │  │ └──────────────────┘   │ │
│  └───────────────────────┘  │                        │ │
│          ↓                   │        ↓               │ │
│   Azure Service Bus          │  Azure Service Bus     │ │
│   (Premium tier, HA)         │  (Premium tier, HA)    │ │
│          ↓                   │        ↓               │ │
│  PostgreSQL (Active-Active replication)              │ │
│  ├─ Primary (US-East)                               │ │
│  └─ Read Replica (EU-West)                          │ │
│                                                      │ │
│  Redis Cache (Premium, clustered)                   │ │
│  ├─ US-East replication                            │ │
│  └─ EU-West replication                            │ │
│                                                      │ │
│  CDN (Azure Front Door)                            │ │
│  ├─ Static assets (Next.js /public)                │ │
│  └─ API caching (triage results, etc.)             │ │
│                                                      │ │
└──────────────────────────────────────────────────────┘

Auto-scaling: pods scale 1–10 based on queue depth + CPU
Circuit breakers: fail fast if downstream (Azure OpenAI) is slow
Health checks: liveness + readiness probes per pod
Network policies: pod-to-pod rules for zero-trust networking
```

**Cost per month (1M emails/day across 2 regions):**
```
────────────────────────────────────────────────────────
KUBERNETES INFRASTRUCTURE:
────────────────────────────────────────────────────────
AKS Cluster (2 regions × 1):           $73 × 2        = $146
Worker Nodes (2 regions × 10 nodes × Standard_B4ms):
  = 20 nodes × $180/mo                                = $3,600

Backend Pod replicas (5 per region):   [included in nodes]
Frontend Pod replicas (3 per region):  [included in nodes]
Worker Pod replicas (10 per region):   [included in nodes]

Load Balancers (2× Azure LB):          $25 × 2        = $50
────────────────────────────────────────────────────────
DATABASE:
────────────────────────────────────────────────────────
PostgreSQL (2 regions, HA, 2 vCores):  $300 × 2       = $600
Database backups (7-day retention):    ~$100

Redis Premium (6 shards, clustered):   $1,500
────────────────────────────────────────────────────────
MESSAGING & CACHE:
────────────────────────────────────────────────────────
Azure Service Bus Premium:             $500
────────────────────────────────────────────────────────
CDN & NETWORKING:
────────────────────────────────────────────────────────
Azure Front Door (Premium):            $200
Data egress (inter-region):            ~$200

────────────────────────────────────────────────────────
SUBTOTAL INFRASTRUCTURE:               ~$6,946/month
────────────────────────────────────────────────────────

LLM API COSTS (1M emails/day):
────────────────────────────────────────────────────────
Triage LLM:  1M × $0.015                       = $15,000
Draft LLM:   1M × $0.02                        = $20,000
Commitment:  1M × $0.005 (cheaper, fallback)   = $5,000
────────────────────────────────────────────────────────
SUBTOTAL LLM:                           ~$40,000/month
────────────────────────────────────────────────────────

OBSERVABILITY:
────────────────────────────────────────────────────────
Datadog / New Relic (1M spans/day):     ~$2,000
PagerDuty (incident mgmt):              ~$500
────────────────────────────────────────────────────────

════════════════════════════════════════════════════════
TOTAL MONTHLY (production, 1M emails/day):  ~$49,500/month
════════════════════════════════════════════════════════

Cost per email:  $49,500 / 1,000,000 = $0.05/email
Cost per user (10K concurrent users): $4.95/user/month
```

---

## 3. DEPLOYMENT GUIDE

### Prerequisites

```bash
# Install tools
brew install docker docker-compose terraform azure-cli kubectl

# Login to cloud providers
az login
aws configure
```

### Development → Staging → Production progression

#### Step 1: Commit infrastructure-as-code

```bash
# Staging (terraform + docker)
cd infrastructure/terraform/staging/
terraform plan
terraform apply

# Result: all cloud resources provisioned
```

#### Step 2: Deploy code

```bash
# Build & push containers
docker build -t mailmind-backend:latest ./backend
docker push myregistry.azurecr.io/mailmind-backend:latest

# Deploy to AKS
kubectl apply -f k8s/staging/namespace.yaml
kubectl apply -f k8s/staging/deployment.yaml
kubectl rollout status deployment/backend -n mailmind-staging

# Verify health
kubectl logs -n mailmind-staging deployment/backend -f
```

#### Step 3: Database migrations

```bash
# Run migrations
kubectl exec -it $(kubectl get pod -n mailmind-staging -l app=backend -o name | head -1) \
  -n mailmind-staging -- \
  alembic upgrade head
```

#### Step 4: Promote to production

```bash
# Tag stable release
git tag -a v2.0.0 -m "Production release"
git push origin v2.0.0

# Deploy to prod with blue-green strategy
kubectl set image deployment/backend-prod \
  backend=myregistry.azurecr.io/mailmind-backend:v2.0.0 \
  -n mailmind-prod

# Monitor rollout
kubectl rollout status deployment/backend-prod -n mailmind-prod --timeout=5m
```

---

## 4. QUEUE & WORKER IMPLEMENTATION

### Add to `requirements.txt`

```
redis==5.0.0              # Python Redis client
celery==5.4.0             # Task queue (alternative: RQ)
sqlalchemy==2.0.0         # ORM for PostgreSQL
alembic==1.14.0           # DB migrations
psycopg2-binary==2.9.0    # PostgreSQL adapter
pydantic-settings==2.0.0  # Config management
```

### New files to create

**`app/config/settings.py`** (extend existing)
```python
class Settings:
    # Queue configuration
    QUEUE_BACKEND: str = "redis"  # "memory" | "redis" | "servicebus"
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # Worker configuration
    WORKER_COUNT: int = 1  # overridden by K8s replicas
    MAX_RETRIES: int = 3
    RETRY_DELAY_SECONDS: int = 300
    
    # Database
    DATABASE_URL: str = "postgresql://user:pass@localhost/mailmind"
    
    # Result caching (same Redis)
    RESULT_CACHE_TTL_SECONDS: int = 86400  # 1 day
```

**`app/queue/redis_queue.py`** (new)
```python
import redis
import json
from app.config.settings import settings

class RedisQueue:
    def __init__(self):
        self.r = redis.from_url(settings.REDIS_URL)
    
    def enqueue(self, job: dict):
        self.r.lpush("mailmind:queue:enrichment", json.dumps(job))
    
    def dequeue(self):
        job = self.r.rpop("mailmind:queue:enrichment")
        return json.loads(job) if job else None
    
    def requeue(self, job: dict, delay_secs: int = 300):
        self.r.expire(json.dumps(job), delay_secs)
        self.enqueue(job)
    
    def depth(self):
        return self.r.llen("mailmind:queue:enrichment")
```

**`app/workers/enrichment.py`** (new)
```python
import time
import logging
from app.queue.redis_queue import RedisQueue
from app.agents.nodes import commitment_node, calendar_node, rag_node, gate_node
from app.services.pii import restore_text
from app.services.storage import save_enrichment_result

logger = logging.getLogger(__name__)
queue = RedisQueue()

def worker():
    """Background worker: dequeue emails, enrich, store results."""
    while True:
        job = queue.dequeue()
        if not job:
            time.sleep(1)
            continue
        
        email_id = job["email_id"]
        state = job["state"]
        
        try:
            # Continue from triage result
            state.update(commitment_node(state))
            state.update(calendar_node(state))
            state.update(rag_node(state))
            state.update(gate_node(state))
            
            # Restore PII
            mapping = state.get("mask_mapping", {})
            if state.get("draft_reply"):
                state["draft_reply"] = restore_text(state["draft_reply"], mapping)
            
            # Save to DB
            save_enrichment_result(email_id, state)
            logger.info(f"Enrichment complete: {email_id}")
            
        except Exception as e:
            logger.error(f"Enrichment failed: {email_id}: {e}")
            # Retry with exponential backoff
            queue.requeue(job, delay_secs=300 * (job.get("retry_count", 0) + 1))

if __name__ == "__main__":
    worker()
```

**`app/services/storage.py`** (new)
```python
from sqlalchemy import create_engine, Column, String, JSON, DateTime
from sqlalchemy.orm import declarative_base, Session
from datetime import datetime, timezone
from app.config.settings import settings

engine = create_engine(settings.DATABASE_URL)
Base = declarative_base()

class EmailEnrichment(Base):
    __tablename__ = "email_enrichment"
    email_id = Column(String, primary_key=True)
    triage_result = Column(JSON)
    commitments = Column(JSON)
    draft_reply = Column(String)
    conflict_summary = Column(String)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

def save_enrichment_result(email_id: str, state: dict):
    with Session(engine) as session:
        result = EmailEnrichment(
            email_id=email_id,
            triage_result={"priority": state.get("priority"), "score": state.get("composite_score")},
            commitments=state.get("commitments"),
            draft_reply=state.get("draft_reply"),
            conflict_summary=state.get("conflict_summary"),
        )
        session.add(result)
        session.commit()

def get_enrichment_result(email_id: str):
    with Session(engine) as session:
        result = session.query(EmailEnrichment).filter_by(email_id=email_id).first()
        return result.__dict__ if result else None
```

**Kubernetes deployment** (`k8s/staging/deployment.yaml`)
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: mailmind-backend
spec:
  replicas: 2
  selector:
    matchLabels:
      app: backend
  template:
    metadata:
      labels:
        app: backend
    spec:
      containers:
      - name: backend
        image: myregistry.azurecr.io/mailmind-backend:latest
        ports:
        - containerPort: 8000
        env:
        - name: QUEUE_BACKEND
          value: "redis"
        - name: REDIS_URL
          valueFrom:
            secretKeyRef:
              name: mailmind-secrets
              key: redis-url
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: mailmind-secrets
              key: database-url
        livenessProbe:
          httpGet:
            path: /api/health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10

---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: mailmind-worker
spec:
  replicas: 3
  selector:
    matchLabels:
      app: worker
  template:
    metadata:
      labels:
        app: worker
    spec:
      containers:
      - name: worker
        image: myregistry.azurecr.io/mailmind-backend:latest
        command: ["python", "-m", "app.workers.enrichment"]
        env:
        - name: QUEUE_BACKEND
          value: "redis"
        - name: REDIS_URL
          valueFrom:
            secretKeyRef:
              name: mailmind-secrets
              key: redis-url
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: mailmind-secrets
              key: database-url
        resources:
          requests:
            cpu: 500m
            memory: 512Mi
          limits:
            cpu: 1000m
            memory: 1Gi
```

---

## 5. COST OPTIMIZATION TIPS

### Save on LLM costs
- **Cache triage results** — same email analyzed twice? Skip the API call.
  ```python
  @cache(ttl=3600)
  def triage_email(email_id, sender, subject, body):
      # Hash the content, check cache first
  ```
- **Fallback strategies** — use regex when GPT-4o is too expensive.
  ```python
  if cost > threshold:
      use deterministic commitment extraction (regex)
  else:
      use GPT-4o structured output
  ```
- **Batch API calls** — use Azure OpenAI batch API (40% cheaper, 24h latency).

### Save on infrastructure
- **Use spot instances** (60% cheaper) for workers.
  ```yaml
  nodeSelector:
    cloud.microsoft.com/azure-spot: "true"
  ```
- **Autoscale to zero** — if queue is empty, scale workers to 0.
  ```yaml
  minReplicas: 0
  maxReplicas: 10
  targetQueueDepth: 100
  ```
- **Reserved instances** — 30% discount for 1-year commitment on baseline load.

### Save on data transfer
- **CDN for static assets** — cheap ($10/TB) vs egress ($0.08/GB).
- **Regional caching** — store recent enrichment results in Redis near the user.

---

## 6. COST COMPARISON SUMMARY

| Scenario | Infra | LLM | Total/mo | Per email | Notes |
|---|---|---|---|---|---|
| Dev (local) | $0 | $0 | $0 | $0 | Runs on laptop |
| 100 emails/day | $0 | $3 | $3 | $0.001 | Staging with low volume |
| 10K emails/day | $365 | $350 | $715 | $0.024 | Small startup |
| 100K emails/day | $2,000 | $3,500 | $5,500 | $0.018 | Medium (growth stage) |
| 1M emails/day | $6,946 | $40,000 | $49,500 | $0.050 | Enterprise (2 regions) |

---

## 7. NEXT STEPS

1. **Dev loop** — Use docker-compose locally; all queue ops in-memory.
2. **Staging** — Deploy to Azure with Redis + PostgreSQL + 3 worker replicas.
3. **Load test** — Use k6 or locust to simulate 10K concurrent users.
4. **Production** — Deploy to multi-region Kubernetes with auto-scaling.
5. **Monitor** — Watch queue depth, worker latency, API error rates in Datadog.

Would you like me to implement the database layer and worker threads for you?
