# OASIS Virtual World Platform - Architecture Overview

**Document Version:** 1.0
**Date:** 2026-01-23
**Author:** Chief Technology Architect

---

## Executive Summary

This document outlines a modular, scalable architecture for the OASIS virtual world platform. The design supports progressive scaling from proof-of-concept (50 users) to production (10,000+ concurrent users).

---

## Architecture Principles

1. **Modular Design** - Each component can scale independently
2. **Cloud-Native** - Leverage managed services where possible
3. **GCP-First** - Align with existing TROZLAN infrastructure
4. **Native Client** - No pixel streaming initially (cost/performance)
5. **AI-Integrated** - Claude MCP as first-class citizen

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              OASIS ARCHITECTURE                              │
└─────────────────────────────────────────────────────────────────────────────┘

                              ┌─────────────────┐
                              │   CDN / Edge    │
                              │  (CloudFlare)   │
                              └────────┬────────┘
                                       │
┌──────────────┐              ┌────────▼────────┐              ┌──────────────┐
│ Unity Client │◄────────────►│   API Gateway   │◄────────────►│  Admin Panel │
│  (PC / VR)   │              │  (Cloud Run)    │              │    (Web)     │
└──────────────┘              └────────┬────────┘              └──────────────┘
                                       │
                    ┌──────────────────┼──────────────────┐
                    │                  │                  │
           ┌───────▼───────┐  ┌───────▼───────┐  ┌───────▼───────┐
           │  Game Servers │  │   AI Service  │  │  User Service │
           │  (GKE/Unity)  │  │ (Claude MCP)  │  │  (Firebase)   │
           └───────┬───────┘  └───────┬───────┘  └───────┬───────┘
                   │                  │                  │
           ┌───────▼──────────────────▼──────────────────▼───────┐
           │                    DATA LAYER                        │
           │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │
           │  │  Cloud SQL  │  │    Redis    │  │   Cloud     │  │
           │  │  (Phoenix)  │  │   (Cache)   │  │   Storage   │  │
           │  └─────────────┘  └─────────────┘  └─────────────┘  │
           └──────────────────────────────────────────────────────┘
```

---

## Phase 1: PoC Architecture (10-50 CCU)

```
┌─────────────────────────────────────────────────────────────────┐
│                    POC ARCHITECTURE (Minimal)                    │
└─────────────────────────────────────────────────────────────────┘

  ┌─────────────┐         ┌─────────────┐         ┌─────────────┐
  │Unity Client │────────►│  Single     │────────►│  Cloud SQL  │
  │  (Dev Build)│◄────────│  Game Server│◄────────│  (Phoenix)  │
  └─────────────┘         │  (GCE VM)   │         └─────────────┘
                          └──────┬──────┘
                                 │
                          ┌──────▼──────┐
                          │ Claude API  │
                          │ (Direct)    │
                          └─────────────┘

  Components:
  • 1x GCE VM (c2-standard-8) - Game server
  • 1x Cloud SQL (db-standard-2) - Player/world state
  • Firebase Auth - User authentication
  • Claude API - AI generation (direct calls)
  • Cloud Storage - Asset storage

  Monthly Cost: $1,200 - $5,700
```

---

## Phase 2: Alpha Architecture (100-500 CCU)

```
┌─────────────────────────────────────────────────────────────────┐
│                    ALPHA ARCHITECTURE (Multi-Region)             │
└─────────────────────────────────────────────────────────────────┘

                         ┌─────────────────┐
                         │  Cloud Load     │
                         │  Balancer       │
                         └────────┬────────┘
                                  │
         ┌────────────────────────┼────────────────────────┐
         │                        │                        │
  ┌──────▼──────┐         ┌──────▼──────┐         ┌──────▼──────┐
  │ us-central1 │         │ us-east1    │         │ europe-west1│
  │ ┌─────────┐ │         │ ┌─────────┐ │         │ ┌─────────┐ │
  │ │ GKE Pod │ │         │ │ GKE Pod │ │         │ │ GKE Pod │ │
  │ │ (Unity) │ │         │ │ (Unity) │ │         │ │ (Unity) │ │
  │ └─────────┘ │         │ └─────────┘ │         │ └─────────┘ │
  └──────┬──────┘         └──────┬──────┘         └──────┬──────┘
         │                        │                        │
         └────────────────────────┼────────────────────────┘
                                  │
                    ┌─────────────┴─────────────┐
                    │                           │
             ┌──────▼──────┐             ┌──────▼──────┐
             │  Cloud SQL  │             │  MCP Server │
             │  (HA Pair)  │             │  (Claude)   │
             └─────────────┘             └─────────────┘

  Components:
  • GKE Autopilot - Container orchestration
  • 3 regions - Low latency globally
  • Cloud SQL HA - High availability database
  • MCP Server - Dedicated AI integration
  • Redis - Session caching
  • Cloud CDN - Asset delivery

  Monthly Cost: $10,500 - $44,500
```

---

## Phase 3: Production Architecture (1,000+ CCU)

```
┌─────────────────────────────────────────────────────────────────┐
│                 PRODUCTION ARCHITECTURE (Global)                 │
└─────────────────────────────────────────────────────────────────┘

                              ┌─────────────┐
                              │  Cloudflare │
                              │     CDN     │
                              └──────┬──────┘
                                     │
                              ┌──────▼──────┐
                              │   Global    │
                              │   L7 LB     │
                              └──────┬──────┘
                                     │
    ┌────────────────────────────────┼────────────────────────────────┐
    │                                │                                │
┌───▼───┐                       ┌────▼────┐                      ┌────▼────┐
│  NAM  │                       │   EUR   │                      │  APAC   │
│       │                       │         │                      │         │
│┌─────┐│                       │┌───────┐│                      │┌───────┐│
││Agones││                       ││Agones ││                      ││Agones ││
││Fleet ││                       ││Fleet  ││                      ││Fleet  ││
│└──┬──┘│                       │└───┬───┘│                      │└───┬───┘│
│   │   │                       │    │    │                      │    │    │
│┌──▼──┐│                       │┌───▼───┐│                      │┌───▼───┐│
││Redis ││                       ││Redis  ││                      ││Redis  ││
│└─────┘│                       │└───────┘│                      │└───────┘│
└───┬───┘                       └────┬────┘                      └────┬────┘
    │                                │                                │
    └────────────────────────────────┼────────────────────────────────┘
                                     │
                              ┌──────▼──────┐
                              │   Cloud     │
                              │   Spanner   │
                              │  (Global)   │
                              └──────┬──────┘
                                     │
                    ┌────────────────┴────────────────┐
                    │                                 │
             ┌──────▼──────┐                  ┌──────▼──────┐
             │  AI Cluster │                  │   Phoenix   │
             │  (MCP+Cache)│                  │   DB Link   │
             └─────────────┘                  └─────────────┘

  Components:
  • Agones - Game server orchestration (auto-scaling)
  • Cloud Spanner - Global strong consistency
  • Multi-region Redis - Session/AI caching
  • Dedicated AI cluster - MCP + semantic caching
  • Phoenix DB integration - Cross-TROZLAN data

  Monthly Cost: $230,000 - $650,000 (at 10K CCU)
```

---

## Key Data Flows

### Player Login Flow
```
Client → Firebase Auth → API Gateway → User Service → Cloud SQL
                                    ↓
                              Session Token
                                    ↓
                              Matchmaking → Game Server Assignment
```

### World State Sync Flow
```
Client Action → Game Server → Validate → Cloud SQL (persist)
                           ↓
                    Broadcast to other clients in world
```

### AI Generation Flow
```
User Prompt → Game Server → MCP Server → Claude API
                                      ↓
                               Cache Check (Redis)
                                      ↓
                               Response → Asset Generation
                                      ↓
                               Client Render
```

---

## TROZLAN Integration Points

| TROZLAN Service | Integration | Purpose |
|-----------------|-------------|---------|
| Phoenix DB (Cloud SQL) | Direct | Unified player identity |
| BotSentinel | API | UGC moderation |
| Claude MCP | Native | AI generation |
| Gensona | Future | Voice/avatar |

---

## Technology Decisions

| Component | Choice | Rationale |
|-----------|--------|-----------|
| Game Engine | Unity (PoC) | Runtime glTF (glTFast), C# AI-agent codegen, fast iteration — see ADR-0001. Production engine re-evaluated at Gate 1→2 |
| Cloud Provider | GCP | Existing TROZLAN infra, Agones support |
| Database (PoC/Alpha) | Cloud SQL | Familiar, Phoenix integration |
| Database (Prod) | Cloud Spanner | Global consistency |
| Orchestration | Agones | Open-source, GKE-native, proven |
| AI Integration | Claude MCP | Protocol standard, tool ecosystem |
| Auth | Firebase | TROZLAN ecosystem alignment |
| CDN | Cloudflare | Performance, DDoS protection |

---

## Scaling Considerations

| Scale | Game Servers | Database | AI Cluster |
|-------|--------------|----------|------------|
| 50 CCU | 1-2 VMs | Cloud SQL | Direct API |
| 500 CCU | 8-20 pods | Cloud SQL HA | Dedicated MCP |
| 5,000 CCU | 150-350 pods | Cloud Spanner | Clustered + cache |
| 10,000 CCU | 300-700 pods | Cloud Spanner | Multi-region |

---

## Security Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      SECURITY BOUNDARIES                         │
└─────────────────────────────────────────────────────────────────┘

  Internet          │  DMZ           │  Private VPC    │  Data
  ──────────────────┼────────────────┼─────────────────┼──────────
                    │                │                 │
  [Clients] ───────►│ [API Gateway] │ [Game Servers]  │ [Databases]
                    │ [CDN]         │ [AI Services]   │ [Storage]
                    │                │                 │
                    │  WAF + DDoS   │  VPC Firewall   │  IAM + CMEK
```

---

## Next Steps

1. **Week 1-2:** Set up GCP project, VPC, basic infrastructure
2. **Week 3-4:** Deploy single headless Unity dedicated server, basic auth
3. **Week 5-6:** Claude API integration, first AI generation
4. **Week 7-8:** Integration testing, performance baseline

---

*Architecture designed for incremental validation and scaling.*
