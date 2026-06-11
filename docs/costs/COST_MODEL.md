# OASIS Virtual World Initiative - Cost Model Analysis

## Chief Financial Analytics Officer Assessment

**Document Classification:** Financial Planning - ESTIMATES ONLY
**Prepared by:** CFAO
**Date:** January 23, 2026

---

## CRITICAL DISCLAIMER

**ALL FIGURES IN THIS DOCUMENT ARE ESTIMATES** based on:
- Publicly available cloud provider pricing (AWS, GCP)
- Industry benchmarks for similar virtual world projects
- Standard software engineering salary ranges

**Confidence Levels:**
- **HIGH (70-90%):** Published pricing with clear usage patterns
- **MEDIUM (50-70%):** Interpolated from similar projects
- **LOW (30-50%):** Significant unknowns, wide variance expected

---

## Scenario 1: Proof of Concept Phase

**Duration:** 3-4 months | **CCU:** 10-50 | **Region:** Single (US)

### Infrastructure Costs (Monthly)

| Component | Low | High | Confidence |
|-----------|-----|------|------------|
| Compute (Game Servers) | $500 | $1,500 | HIGH |
| Database | $200 | $500 | HIGH |
| Storage/CDN | $100 | $300 | HIGH |
| Networking | $50 | $200 | MEDIUM |
| AI API (Claude) | $200 | $800 | MEDIUM |
| Monitoring/Logging | $100 | $300 | HIGH |
| **TOTAL MONTHLY** | **$1,200** | **$5,700** | |

### Team Costs (Monthly)

| Role | Count | Low | High |
|------|-------|-----|------|
| Senior Engineer | 1-2 | $15,000 | $30,000 |
| Mid-Level Engineer | 1-2 | $10,000 | $20,000 |
| Contract 3D Artist | 0.5 | $0 | $8,000 |
| DevOps/SRE | 0.5 | $5,000 | $10,000 |
| **TOTAL MONTHLY** | | **$30,000** | **$68,000** |

### PoC Phase Summary

| Metric (ESTIMATE) | Low | High |
|-------------------|-----|------|
| Monthly burn | $31,200 | $73,700 |
| Phase-only investment (4 months) | $125,800 | $305,800 |

**Rounded canonical Phase 1 estimate:** $126K - $306K phase-only and cumulative
through Month 4.

---

## Scenario 2: Alpha Phase

**Duration:** 9-12 months | **CCU:** 100-500 | **Regions:** 2-3

### Infrastructure Costs (Monthly)

| Component | Low | High |
|-----------|-----|------|
| Compute (Game Servers) | $3,000 | $10,000 |
| Database | $800 | $2,500 |
| Storage/CDN | $500 | $2,000 |
| Networking | $500 | $3,000 |
| AI API (Claude) | $1,000 | $5,000 |
| Pixel Streaming (if used) | $4,000 | $20,000 |
| Monitoring | $500 | $1,500 |
| **TOTAL (No Streaming)** | **$6,500** | **$24,500** |
| **TOTAL (With Streaming)** | **$10,500** | **$44,500** |

### Alpha Phase Summary

| Metric (ESTIMATE) | Low | High |
|-------------------|-----|------|
| Monthly burn | $113,500 | $234,500 |
| Phase-only investment (12 months) | $1,404,000 | $2,969,000 |

**Rounded canonical Phase 2 estimate:** $1.404M - $2.969M phase-only. Added to
Phase 1, this reconciles to $1.53M - $3.28M cumulative through Month 16.

---

## Scenario 3: Production Phase

### Infrastructure by Scale (Monthly, No Pixel Streaming)

| CCU | Compute | Database | Storage | Network | AI | Total |
|-----|---------|----------|---------|---------|-----|-------|
| 1,000 | $15-35K | $3-8K | $2-6K | $5-15K | $5-15K | **$33-87K** |
| 5,000 | $60-150K | $10-25K | $8-20K | $20-60K | $20-60K | **$126-335K** |
| 10,000 | $100-280K | $20-50K | $15-40K | $40-120K | $40-120K | **$230-650K** |

### WITH Pixel Streaming (Major Cost Driver)

| CCU | Without Streaming | With Streaming | Difference |
|-----|-------------------|----------------|------------|
| 1,000 | $33-87K | $73-167K | +$40-80K |
| 5,000 | $126-335K | $326-735K | +$200-400K |
| 10,000 | $230-650K | $630-1,450K | +$400-800K |

**⚠️ RECOMMENDATION: Avoid pixel streaming at scale - native clients only**

---

## Cost Per Concurrent User Analysis

**Basis:** these figures are the **fully-burdened monthly burn (team + infrastructure)
divided by CCU** — *not* the infrastructure-only tables above. Derivations:

- PoC: monthly burn $31.2K–$73.7K (PoC Phase Summary) ÷ 50 CCU
- Alpha: monthly burn $113.5K–$234.5K (Alpha Phase Summary) ÷ 500 CCU
- Production 1,000: Year-2 phase-only $3.53M–$7.92M ÷ 12 months ÷ 1,000 CCU
- Production 5,000: Year-3 phase-only $4.64M–$10.9M ÷ 12 months ÷ 5,000 CCU
- Production 10,000: same team-cost assumption plus the 10K-CCU infrastructure range ÷ 10,000 CCU

| Phase | CCU | Cost/User/Month (team + infra) |
|-------|-----|--------------------------------|
| PoC | 50 | $624 - $1,474 |
| Alpha | 500 | $227 - $469 |
| Production | 1,000 | $294 - $660 |
| Production | 5,000 | $77 - $182 |
| Production | 10,000 | $49 - $122 |

**Key Insight:** 80-90% cost reduction per user from PoC to production scale.

---

## Break-Even Analysis

### Revenue Requirements

The rows below use the midpoint of the existing **Production Phase / No Pixel
Streaming** monthly infrastructure ranges above. They are ESTIMATES and are not a
new pricing model.

| CCU | Existing monthly range (No Streaming, ESTIMATE) | Monthly Cost Midpoint (ESTIMATE) | Break-Even/User |
|-----|--------------------------------------------------|----------------------------------|-----------------|
| 1,000 | $33K-$87K | $60,000 | $60/user/month |
| 5,000 | $126K-$335K | $230,500 | $46/user/month |
| 10,000 | $230K-$650K | $440,000 | $44/user/month |

### Monetization Scenarios

The rows below use the same existing 10,000-CCU no-streaming midpoint estimate
($440K/month) from the table above.

| Model | Revenue/User | CCU for Break-Even (ESTIMATE) |
|-------|--------------|-------------------------------|
| Subscription ($15/mo) | $15 | ~30,000 CCU |
| Subscription ($30/mo) | $30 | ~15,000 CCU |
| Premium ($50/mo) | $50 | ~9,000 CCU |
| Enterprise (B2B) | $200+ | ~2,200 CCU |

---

## Cost Optimization Opportunities

| Optimization | Potential Savings |
|--------------|-------------------|
| Reserved instances (1-3yr) | 30-60% on compute |
| Spot/preemptible instances | 60-80% on batch |
| Right-sizing instances | 20-40% on compute |
| CDN caching optimization | 30-50% on data transfer |
| Avoid pixel streaming | 60-80% of streaming cost |
| AI prompt optimization | 30-50% on API costs |

---

## Cumulative Investment Timeline

Canonical reading:

- **Phase-only estimate** = incremental cost for that phase.
- **Cumulative-through estimate** = total cost from Phase 1 start through the milestone.
- All figures in this table are ESTIMATES rounded from existing rows in this document.

| Milestone | Duration | Phase-only estimate | Cumulative-through estimate |
|-----------|----------|---------------------|-----------------------------|
| End of PoC / Phase 1 | Month 4 | $126K-$306K | $126K-$306K |
| End of Alpha / Phase 2 | Month 16 | $1.404M-$2.969M | $1.53M-$3.28M |
| Year 2 (1K CCU) | Month 28 | $3.53M-$7.92M | $5.06M-$11.2M |
| Year 3 (5K CCU) | Month 40 | $4.64M-$10.9M | $9.7M-$22.1M |

The Phase 1 and Phase 2 cumulative estimates align with the roadmap planning
ranges (~$126K-$306K and ~$1.53M-$3.28M). The later phase-only rows are the
existing cumulative deltas shown here only to prevent reading the cumulative totals
as standalone phase budgets.

---

## Cost Warning Signs

| Warning Sign | Threshold | Action |
|--------------|-----------|--------|
| Data transfer > 25% of compute | Alert | Audit CDN |
| AI API > $0.10/user/session | Alert | Prompt optimization |
| Pixel streaming at scale | Critical | Native client strategy |
| On-demand > 30% of compute | Alert | Reserved capacity |

---

## Recommendations

### PoC Phase
- Start with minimal infrastructure
- Avoid pixel streaming
- Use on-demand instances
- Implement cost tagging from day one

### Alpha Phase
- Benchmark actual vs. estimated costs
- Begin reserved capacity planning
- Optimize AI usage patterns

### Production Phase
- Hybrid infrastructure (reserved + evaluate colo)
- Aggressive CDN caching
- Real-time cost monitoring
- Quarterly optimization reviews

---

*All figures are ESTIMATES. Validate with actual deployments.*
