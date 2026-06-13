# MailMind — Workflow Diagrams

Presentation-grade SVG diagrams, one per workflow. SVGs scale infinitely and stay
crisp in PowerPoint / Google Slides. PNG copies (if generated) live in `png/`.

| # | File | Workflow | Best slide |
|---|------|----------|------------|
| 01 | `01-system-architecture.svg` | Full two-tier system architecture | Technical Architecture |
| 02 | `02-oauth-authentication-flow.svg` | OAuth login + token exchange | Technical Architecture |
| 03 | `03-session-auth-rotation.svg` | Cookie session auth + rotation | Security by Design |
| 04 | `04-agentic-pipeline-dag.svg` | **LangGraph agentic pipeline (the centerpiece)** | Technical Architecture / "Genuinely Agentic" |
| 05 | `05-triage-scoring-engine.svg` | 5-axis explainable triage scoring | Trust & Explainability |
| 06 | `06-dashboard-inbox-init.svg` | Dashboard load + inbox init | Solution Demonstration |
| 07 | `07-email-open-parallel-pipeline.svg` | Email open → 6 parallel AI calls | Solution Demonstration |
| 08 | `08-rag-retrieval-flow.svg` | RAG precedent retrieval (ChromaDB) | Personalization Engine |
| 09 | `09-draft-generation-flow.svg` | Draft generation (RAG + Tone DNA) | Personalization Engine |
| 10 | `10-commitment-extraction-flow.svg` | Commitment extraction → tasks/calendar | Solution Demonstration |
| 11 | `11-reply-mark-done-flow.svg` | Reply & mark-as-Done | Solution Demonstration |
| 12 | `12-feedback-submission-flow.svg` | Feedback (DB-first + fallback) | Challenges & Learnings |
| 13 | `13-onboarding-flow.svg` | User onboarding (4 phases) | Solution Demonstration |
| 14 | `14-security-pii-masking.svg` | Security & PII masking (defense in depth) | Security by Design |

## Shared visual language

- **Blue** = frontend / I-O · **Violet** = backend services · **Green** = LLM reasoning (GPT-4o)
- **Teal** = data / infra · **Red** = security / PII · **Yellow** = human supervision / decision

## Regenerating PNGs

```powershell
# requires cairosvg:  python -m pip install cairosvg
python docs/diagrams/render_png.py
```
