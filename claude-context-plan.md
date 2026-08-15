# Architecture Plan

## Context Summary

This plan reviews the `aws-sa` Claude Code skill definition at `/home/devuser/.claude/plugins/wills-plugins/plugins/wills-skills/commands/aws-sa/SKILL.md` for accuracy and completeness against a 2025-2026 senior AWS Solutions Architect benchmark. The goal is to identify what is strong, what is outdated or incorrect, what is missing, and produce an actionable list of changes.

---

## Assessment: What Is Accurate and Strong

The following content is technically correct, well-calibrated to senior-SA level, and does not need to change.

**Mindset and philosophy**
- The "requirements before services" principle with the distinction between design questions (ask for NFRs) and comparative/factual questions (answer directly) is excellent and rare in skill definitions of this type.
- "Every decision is a trade-off, not a best practice" and the trade-off vocabulary table are directly aligned with what distinguishes a senior SA from a junior one.
- "Boring technology is a feature" and "design for the team, not the ideal" are well-framed and actionable.
- The Werner Vogels Frugal Architect reference is current and appropriately weighted.

**Well-Architected Framework**
- All six pillars are present and correctly ordered. This is an explicit pass — many SA prompts still cite only five pillars (pre-Sustainability).
- App Mesh deprecation is correctly captured: "blocked for new customers since September 2024, EOL September 2026."
- VPC Lattice is correctly positioned as the EKS service mesh replacement.
- ECS Service Connect is correctly named as the ECS-native circuit breaker / service mesh mechanism.

**VPC design**
- Three-tier subnet layout (public / private / isolated) is correct and well-explained.
- One NAT Gateway per AZ requirement and the single-AZ dependency risk are correctly flagged.
- Gateway Endpoints free / Interface Endpoints billed distinction is accurate.

**Service decision frameworks**
- Lambda scaling rate (~1,000 environments per 10 seconds) is correct.
- Provisioned Concurrency eliminates cold starts — accurate.
- Lambda SnapStart runtimes are precisely specified (Java 11/17/21 with AL2023 notes, Python 3.12+, .NET 8) — this is the most up-to-date and specific detail in the skill and is correct.
- Aurora Serverless v2 scale-to-zero engine version requirements (MySQL 3.08.0+, PostgreSQL 16.3+/15.7+/14.12+/13.15+) are correct and unusually specific — a genuine senior-SA differentiator.
- DLQ three-layer distinction (SNS subscription DLQ, Lambda async invocation DLQ, SQS queue DLQ) is technically precise and a common area of confusion — this is a strength.
- ElastiCache Valkey preference over Redis OSS 7.2 is current and correct.

**Anti-patterns and gotchas**
- IAM policy evaluation cross-account rule with the KMS exception is technically correct and important.
- CloudTrail global service events logging to us-east-1 is correct.
- RDS Multi-AZ standby not being readable is correct and commonly misunderstood.
- EKS Pod Identity preferred over IRSA for new clusters is current (GA late 2023).
- Static stability principle (never rely on launching resources during an outage) is correctly explained.

**Multi-account and blast radius**
- OU structure is correct and aligned with AWS Control Tower landing zone design.
- IAM Identity Center (never IAM users with passwords) is the current standard.
- Cell-based architecture and shuffle sharding correctly have a "at significant scale" caveat.

**Formatting and response rules**
- Domain-specific NFR tailoring (e-commerce, data pipelines, compliance, multi-tenant SaaS) is excellent — this is a genuinely senior-level addition.
- The IaC review checklist is comprehensive and correct.

---

## Assessment: What Is Outdated or Incorrect

The following items contain errors, omissions, or information the benchmark explicitly flags as out-of-date.

### 1. Aurora Serverless v2 minimum ACU stated incorrectly in the researcher benchmark vs. the skill

The researcher notes "minimum is 0.5 ACU, not zero" and "does not scale to zero." The skill correctly states this and correctly documents the engine versions for true scale-to-zero. However, the skill says "default minimum is 0.5 ACU (~$43/month always billed)" — the dollar figure is an approximation that will drift over time and may already be inaccurate by region. The dollar figure should be removed or described as "approximately $40-50/month depending on region" to avoid becoming a stale number that erodes trust.

### 2. AWS Proton is not mentioned as deprecated

The benchmark explicitly states: "Do not recommend AWS Proton for new internal developer platform builds (EOL October 2026)." The skill has no mention of Proton at all. If a user asks about internal developer platforms or service catalogues, the skill would not flag Proton's EOL status. This is a gap that could result in bad advice.

### 3. CodeCommit and Cloud9 deprecations are absent

The benchmark lists these as services an SA should no longer recommend. The skill has no deprecation warnings at all. A user asking "should I use CodeCommit for our new repo?" or "set up a Cloud9 environment" would get no deprecation signal from this skill.

### 4. QLDB is missing from deprecation warnings

QLDB reached EOL July 31, 2025. An SA should redirect any QLDB question to Aurora PostgreSQL ledger pattern or DynamoDB with versioning. The skill does not mention this.

### 5. Savings Plans trade-off row is incomplete

The trade-off table row for Savings Plans says "Up to 66% (Compute, 3-yr all-upfront); ~40% on 1-yr. Up to 72% for EC2 Instance Savings Plans (3-yr all-upfront)" — but the researcher benchmark documents that AWS Database Savings Plan (December 2025) now covers RDS, Aurora, DynamoDB, ElastiCache, and DocumentDB for up to 35% savings. This is a significant new commitment option that the skill should reference, particularly since the skill covers database architecture extensively.

### 6. Performance Efficiency pillar caching layer is partially outdated

The caching section says "ElastiCache Valkey / Redis" correctly, but does not mention ElastiCache Serverless (GA 2024), which is the recommended starting point for new ElastiCache deployments when traffic is unpredictable. The skill's caching layer list would lead a user to provision a fixed ElastiCache cluster when ElastiCache Serverless may be the right default.

### 7. EKS section missing Karpenter recommendation

The skill mentions EKS and Kubernetes ecosystem tooling but does not mention Karpenter as the recommended node autoscaler for EKS, which reached 1.0 GA in 2024 and is now AWS's recommended replacement for Cluster Autoscaler. Any EKS discussion should include Karpenter.

### 8. Control plane vs. data plane awareness is mentioned but not named

The skill alludes to the control plane / data plane distinction in the static stability principle ("control planes can be impaired when you need them most"), but never explicitly names the concept. The benchmark flags this as a key senior SA differentiator. The skill should explicitly name Route 53 ARC and Global Accelerator as data-plane failover mechanisms vs. Auto Scaling / CloudFormation as control-plane operations that may be degraded during regional events.

### 9. GuardDuty multi-region requirement absent

The benchmark explicitly flags: "GuardDuty must be enabled in every region. Use AWS Organizations delegated admin to enable GuardDuty org-wide from the security account." The skill mentions GuardDuty + Security Hub as components of the Security pillar, but never specifies the multi-region requirement or the delegated admin pattern. This is a common production gap.

### 10. gp2 vs. gp3 EBS migration is not mentioned

The skill mentions EBS in the storage decision framework but does not flag the gp2 → gp3 migration opportunity, which is near-universal cost savings and is flagged by the benchmark as a key cost gotcha. The IaC review checklist should flag gp2 volume types.

---

## Assessment: What Is Missing

The following topics are covered in the benchmark as required senior-SA knowledge but are entirely absent from the skill.

### Missing Topic 1: Generative AI / Bedrock architecture

The benchmark dedicates a full section to GenAI/AI workloads as a "2025-2026 addition" that distinguishes senior SAs. The skill has zero content on:
- Amazon Bedrock (VPC endpoint requirement, IAM model access, Knowledge Bases / RAG pattern, Guardrails, AgentCore)
- Vector store selection for RAG (Aurora PostgreSQL pgvector vs. OpenSearch Serverless vs. Bedrock Knowledge Bases native)
- Token cost management (model selection, caching, prompt design)
- When to fine-tune vs. prompt-engineer vs. RAG

A senior SA in 2025-2026 who cannot advise on embedding Bedrock securely into application architecture is not current.

### Missing Topic 2: Observability tooling specifics

The skill lists "structured logs + distributed traces (X-Ray) + p99 metrics is the minimum" in the anti-patterns section but provides no observability decision framework. Missing:
- AWS Distro for OpenTelemetry (ADOT) as the recommended path for new instrumentation (vendor-neutral, portable)
- CloudWatch Application Signals (native APM on OpenTelemetry; SLO/SLI tracking; auto-instrumentation for Java/Python/.NET)
- Embedded Metrics Format (EMF) for Lambda custom metrics
- The distinction between Managed Grafana / Managed Prometheus for teams bringing their own stack
- CloudWatch Synthetics canaries for endpoint monitoring

### Missing Topic 3: Networking — Transit Gateway and PrivateLink patterns

The skill covers VPC design well but has no content on Transit Gateway (hub-and-spoke for multi-VPC connectivity), VPC Peering non-transitivity, PrivateLink (how and when to use for cross-account service sharing), or Direct Connect with MACsec. These are standard architecture decisions in any multi-account landing zone and multi-team platform.

### Missing Topic 4: Global Accelerator vs. Route 53 failover distinction

The benchmark identifies this as important: Global Accelerator provides data-plane failover (no DNS TTL delays) whereas Route 53 health check failover depends on DNS propagation (TTL-bounded). The skill mentions neither Global Accelerator nor this distinction. This matters for DR and availability SLA design.

### Missing Topic 5: AWS Resilience Hub

The benchmark flags Resilience Hub as the standard tool for continuously validating RTO/RPO targets. The skill mentions FIS for chaos engineering but does not mention Resilience Hub. These are complementary: FIS injects failures; Resilience Hub validates that architecture meets its RTO/RPO targets.

### Missing Topic 6: S3 advanced features

The skill treats S3 as a basic object store. Missing:
- S3 Express One Zone (directory bucket, 10x lower latency, single-AZ, GA 2023) — relevant for latency-sensitive workloads
- S3 Versioning + Object Lock (WORM) — required for compliance workloads (PCI, HIPAA)
- S3 Replication (CRR / SRR) — required for DR and data residency patterns
- S3 Lifecycle policies — foundational cost optimisation

### Missing Topic 7: Graviton recommendation

The benchmark explicitly states "Graviton should be default for new Lambda, ECS, RDS deployments" (20-40% cost reduction vs. x86). The skill does not mention Graviton at all. This is a straightforward cost optimisation that a senior SA should recommend by default for every greenfield workload.

### Missing Topic 8: FSx family for specialised storage

The skill covers EBS, EFS, and S3 but not FSx (Windows File Server for SMB/AD, Lustre for HPC/ML, NetApp ONTAP for multi-protocol, OpenZFS). A user asking about HPC, ML training data storage, or Windows file share workloads would get no guidance.

### Missing Topic 9: Database breadth — Redshift, Neptune, MemoryDB, Timestream

The skill covers RDS, Aurora, DynamoDB, and ElastiCache. Missing entirely: Redshift (data warehouse), Neptune (graph), MemoryDB for Redis (durable in-memory vs. ElastiCache Redis which is cache-first), Timestream (time-series). A senior SA needs to be able to route a user to the right database for their access pattern.

### Missing Topic 10: EventBridge Scheduler vs. CloudWatch Events

The benchmark notes EventBridge Scheduler (GA 2022, now preferred) replaces CloudWatch Events rules for scheduling. The skill covers EventBridge Pipes and event bus correctly but does not mention Scheduler. A user building any scheduled workload would get outdated guidance.

### Missing Topic 11: VPC IP Address Manager (IPAM) and CIDR planning

The benchmark flags VPC CIDR planning and IPAM as important. The skill mentions CIDR sizing guidelines but not AWS IPAM for centralised IP address space management, which is the recommended tool for multi-account organisations.

### Missing Topic 12: Security Hub as aggregation and compliance benchmark tool

The skill mentions Security Hub as a component ("GuardDuty + Security Hub enabled") but does not explain what Security Hub does: aggregates findings from GuardDuty, Inspector, Macie, Config, and IAM Access Analyzer; evaluates against FSBP (Foundational Security Best Practices) and CIS benchmarks. This is the compliance-automation layer a senior SA should describe to any customer concerned with continuous compliance.

### Missing Topic 13: AWS Backup for centralised cross-account backup

AWS Backup is not mentioned. It is the standard tool for centralised backup policy across EBS, RDS, DynamoDB, EFS, FSx, EC2 — including cross-account and cross-region backup vaults. Any discussion of DR or data protection should reference it.

### Missing Topic 14: Deprecation warnings section

The skill has no consolidated deprecation section. A skill review for correctness should actively steer users away from deprecated services. The following should be added as a standalone "Do Not Recommend" list:
- CodeCommit (closed to new customers)
- Cloud9 (closed July 2024)
- OpsWorks (EOL May 2024)
- QLDB (EOL July 2025)
- AWS Proton (EOL October 2026)
- App Mesh (blocked new customers September 2024, EOL September 2026) — already in the body, but should be in a summary list
- CodeCatalyst (maintenance phase, no new features)
- S3 Object Lambda (maintenance phase)
- Greengrass v1 (use v2)

---

## Impacted Files

The only file that needs to be modified is the skill definition:

- `/home/devuser/.claude/plugins/wills-plugins/plugins/wills-skills/commands/aws-sa/SKILL.md` — the skill file to be edited

No new files need to be created. The `claude-context-plan.md` in `/workspace/active_repo/` is created by this planning step.

---

## Step-by-Step Execution Plan

Each step is independently testable by reviewing the SKILL.md diff for that section.

- **Step 1: Add a "Do Not Recommend (Deprecated Services)" section** after the Anti-Patterns section. List: CodeCommit, Cloud9, OpsWorks, QLDB (with Aurora PostgreSQL ledger / DynamoDB alternative), AWS Proton (with Backstage/CDK Pipelines alternative), App Mesh (already noted in body — include here for completeness), CodeCatalyst and S3 Object Lambda (maintenance phase), Greengrass v1. One sentence per service: what it was, why not to use it, what to use instead.

- **Step 2: Add a Generative AI / Bedrock Architecture section** after the Messaging and Orchestration sub-section (or as a new top-level section "AI/ML Workloads"). Cover: Bedrock overview and VPC endpoint requirement, IAM model access model, Knowledge Bases / RAG pattern with vector store options (Aurora PostgreSQL pgvector, OpenSearch Serverless, Bedrock native), Guardrails for content filtering, AgentCore for production agents, token cost management and model selection trade-offs (Haiku vs. Sonnet vs. Opus tier mapped to cost/latency), when to RAG vs. fine-tune vs. prompt-engineer.

- **Step 3: Expand the Observability section** from a one-line anti-pattern mention to a decision framework. Add: ADOT as recommended instrumentation path, CloudWatch Application Signals (SLO/SLI, auto-instrumentation), EMF for Lambda, Synthetics canaries, and when to use Managed Grafana/Prometheus. Keep it concise — one paragraph with a decision table.

- **Step 4: Add Graviton as default compute recommendation** in the Compute decision framework section. Add a bullet after the Lambda/ECS/EKS/EC2 flow chart: "Default instance architecture: Graviton (ARM64) for all new Lambda, ECS, EKS node groups, and RDS deployments. 20-40% cost reduction vs. x86 equivalent. No reason to choose x86 for new greenfield workloads unless the application has a hard x86 dependency (proprietary binaries, x86-only libraries)."

- **Step 5: Add ElastiCache Serverless to the Caching Layers section** as the recommended starting point for new ElastiCache deployments with unpredictable traffic, before committing to a fixed cluster. Update the caching layer entry to read: "ElastiCache Valkey / Redis — hot application data, sessions, computed aggregates. Start with ElastiCache Serverless (2024, auto-scales, per-request pricing) for new deployments; provision a fixed cluster only when predictable throughput justifies committed capacity."

- **Step 6: Add Karpenter recommendation to the EKS section** in the Compute decision framework. After the EKS bullet, add: "EKS node autoscaling: use Karpenter (1.0 GA 2024) by default; it significantly outperforms Cluster Autoscaler and is AWS's recommended approach. Cluster Autoscaler remains supported for existing clusters."

- **Step 7: Add Global Accelerator and the control plane vs. data plane distinction** to Key Production Gotchas and/or the Reliability pillar. Add a named gotcha: "Control plane vs. data plane during regional events — during a large-scale AWS regional event, control plane APIs (EC2 RunInstances, Auto Scaling triggered scale-out, CloudFormation stack updates) may be impaired before or alongside data plane degradation. Design failover to use pre-provisioned capacity (warm standby or hot standby) and data-plane routing mechanisms: Route 53 ARC (Application Recovery Controller) and Global Accelerator. Global Accelerator's static Anycast IP routes to the closest healthy endpoint with no DNS TTL delay — unlike Route 53 failover which is bounded by client-side DNS caching."

- **Step 8: Add AWS Resilience Hub to the DR Strategy section** as the standard RTO/RPO validation tool. After the DR table, add: "Tooling: AWS Resilience Hub continuously validates architecture against defined RTO/RPO targets and produces an assessment score. AWS Fault Injection Simulator (FIS) injects failure scenarios to test recovery procedures. Use both: Resilience Hub tells you whether your architecture meets targets; FIS proves whether your runbooks and automation execute correctly under pressure."

- **Step 9: Add GuardDuty multi-region and delegated admin requirement** to the Security pillar and/or Anti-Patterns section. Add to the Security pillar: "GuardDuty must be enabled in every region, including regions you do not actively use — attackers target unused regions. Enable GuardDuty org-wide via AWS Organizations delegated admin from the Audit/Security account. Do not enable per-account manually."

- **Step 10: Add the Database Savings Plan (December 2025)** to the Cost Optimization pillar and the Trade-off Vocabulary table Savings Plans row. Update to note: AWS Database Savings Plan (launched December 2025) covers RDS, Aurora, DynamoDB, ElastiCache, and DocumentDB for up to 35% savings. Hybrid strategy: Compute Savings Plans for EC2/Fargate/Lambda + Database Savings Plans for database tiers + Spot for interruptible batch.

- **Step 11: Add Networking section for Transit Gateway, PrivateLink, and Global Accelerator** after the VPC Design Fundamentals section. Cover: TGW for multi-VPC hub-and-spoke (VPC peering is not transitive — a common gotcha), PrivateLink for cross-account service sharing, Direct Connect for predictable hybrid latency, Global Accelerator vs. CloudFront (GA = network acceleration + static IP + data plane failover; CloudFront = CDN + edge caching + Lambda@Edge logic).

- **Step 12: Expand the Storage section with S3 advanced features and FSx** in the Storage decision framework. Add: S3 Express One Zone (directory bucket, 10x lower latency, single-AZ, for latency-sensitive workloads), S3 Object Lock / WORM (compliance requirements), S3 Replication (CRR for DR, SRR for cross-account within region), S3 Lifecycle policies (tiering to Intelligent-Tiering by default for unpredictable access). Add FSx row to the storage comparison table: FSx for Windows File Server (SMB/AD), FSx for Lustre (HPC/ML + S3 integration), FSx for NetApp ONTAP (multi-protocol).

- **Step 13: Add expanded database coverage** for Redshift, Neptune, MemoryDB, and Timestream after the RDS vs. DynamoDB section. A simple routing table: "Redshift / Redshift Serverless — columnar analytics warehouse, not OLTP; Neptune — graph data (social networks, fraud detection, knowledge graphs, supply chains); MemoryDB for Redis — durable in-memory (differs from ElastiCache Redis: durability via transaction log, not a cache — use when you need Redis API with database-level durability); Timestream — time-series data (IoT sensor readings, operational metrics at scale)."

- **Step 14: Add EventBridge Scheduler to the Messaging and Orchestration section** as the preferred scheduling mechanism. Update the table to add a row: "EventBridge Scheduler — cron/rate-based scheduled invocations with time zone support, DLQ, and flexible recurring schedules. Preferred over CloudWatch Events rules for all new scheduled workloads."

- **Step 15: Add AWS IPAM to the VPC Design Fundamentals section** as the recommended tool for multi-account CIDR planning. After the CIDR sizing guidance, add: "For multi-account organisations, use AWS VPC IP Address Manager (IPAM) for centralised CIDR allocation and overlap detection across all accounts and regions."

- **Step 16: Add AWS Backup to the Anti-Patterns or DR section** as the standard backup tooling. Note: "AWS Backup provides centralised backup policy management across EBS, RDS, DynamoDB, EFS, FSx, EC2, and Storage Gateway — including cross-account and cross-region backup vaults with immutable vault policies. Missing a centralised backup strategy is an operational anti-pattern."

- **Step 17: Fix the Aurora Serverless v2 dollar figure** in the database section. Replace "~$43/month always billed" with "approximately $40-50/month depending on region (check AWS pricing page for current rate)" to prevent the figure from becoming stale and eroding trust in the skill's accuracy.

- **Step 18: Add Security Hub functional description** to the Security pillar. Expand the current one-line "GuardDuty + Security Hub enabled" to include what Security Hub does: aggregates findings from GuardDuty, Inspector, Macie, Config, and IAM Access Analyzer; continuously evaluates against AWS Foundational Security Best Practices (FSBP) and CIS benchmark standards; provides a centralised compliance dashboard.

- **Step 19: Add gp2 → gp3 migration to the IaC review checklist and Cost section**. In the IaC review response rule, add: "EBS volumes typed as gp2 (should be gp3 — same or better performance, lower cost, migrated with zero downtime via elastic volume modification)." In the Cost pillar, note gp3 as the default.

- **Step 20: Add Responsible AI Lens reference** to the Well-Architected Framework section. After the six pillars, add a note: "Well-Architected Lenses extend the framework for specific domains. Relevant lenses for 2025-2026: Serverless Lens, Data Analytics Lens, ML Lens (updated 2025), Generative AI Lens (updated 2025), Responsible AI Lens (new 2025 — 10 dimensions: controllability, privacy, security, safety, veracity, robustness, fairness, explainability, transparency, governance). Lenses are separate from pillars — do not conflate the two."

---

## Risks and Blockers

**No technical blockers.** The SKILL.md is a Markdown file with YAML frontmatter. All changes are textual additions and edits with no code dependencies.

**Risk 1 — Scope expansion making the skill too long.** The current skill is already thorough (~250 lines of content). Adding all 20 steps could make it significantly longer. Mitigation: keep new sections concise (decision tables and bullet lists, not prose). The skill's value is in decision frameworks and trade-offs, not encyclopaedic service coverage. Prioritise Steps 1, 2, 7, 9, 10, and 14 as the highest-impact changes; the remainder can be added at lower density.

**Risk 2 — Dollar figures and discount percentages becoming stale.** Any specific dollar amounts or percentage discounts in the skill will drift. The Aurora Serverless v2 $43/month figure is already an example. Mitigation: reference ranges ("approximately $40-50/month") and always direct to the AWS pricing page for exact figures.

**Risk 3 — Bedrock section complexity.** Bedrock / GenAI is a large topic. Adding a superficial section is worse than no section (it creates false confidence). Mitigation: keep the Bedrock section focused on architecture decisions (VPC endpoint, IAM model, RAG vs. fine-tune decision, vector store selection) not feature descriptions.

**Risk 4 — Deprecation list becoming stale.** Deprecated services should be reviewed on a schedule — what is currently in maintenance phase may be sunset or EOL by the next time the skill is reviewed. Mitigation: add a "Last reviewed" date to the deprecation section and flag it as requiring quarterly review.

---

## Testing Strategy

Since this is a prompt skill (not executable code), verification is qualitative and scenario-based. After implementing the changes, the following scenarios should be run against the updated skill to verify accuracy and coverage:

1. **Deprecation scenarios:** Ask "should I use CodeCommit for a new repository?", "set up a Cloud9 environment", "use QLDB for an audit log." Each should trigger a deprecation warning with an alternative.

2. **Bedrock / GenAI scenario:** Ask "design a RAG-based customer support chatbot on AWS." The response should include Bedrock Knowledge Bases, VPC endpoint requirement, vector store choice (Aurora pgvector vs. OpenSearch Serverless), Guardrails, and token cost considerations.

3. **DR failover scenario:** Ask "how should we fail over our application during an AWS regional outage?" The response should explicitly mention Route 53 ARC, Global Accelerator, data plane vs. control plane distinction, and pre-provisioned capacity (warm standby).

4. **EKS scenario:** Ask "design an EKS cluster architecture." The response should include Karpenter as the recommended node autoscaler.

5. **Cost optimisation scenario:** Ask "how can we reduce our AWS spend for a workload using RDS Aurora, Lambda, and ElastiCache?" The response should reference Database Savings Plans (December 2025), Graviton instances for Lambda and RDS, ElastiCache Serverless, and gp3 EBS.

6. **GuardDuty scenario:** Ask "how should we configure GuardDuty across our AWS organisation?" The response should specify every-region enablement and delegated admin from the security account.

7. **Observability scenario:** Ask "what observability stack should we use for a new Lambda + API Gateway service?" The response should reference ADOT for instrumentation, CloudWatch Application Signals for SLO/SLI, and EMF for Lambda custom metrics.

8. **Well-Architected Lens scenario:** Ask "what Well-Architected lenses apply to our generative AI workload?" The response should distinguish lenses from pillars and reference the Generative AI Lens and Responsible AI Lens.

9. **IaC review scenario:** Provide a Terraform snippet with a gp2 EBS volume. The IaC review should flag it as should be gp3.

10. **Service comparison scenario:** Ask "what is the difference between ElastiCache Redis and MemoryDB for Redis?" The response should explain that MemoryDB is durable (transaction log) whereas ElastiCache Redis is cache-first, and give guidance on when each is appropriate.

---

**IMPORTANT — handoff to main agent:** This plan is now written to `/workspace/active_repo/claude-context-plan.md`. The Plan Reviewer agent MUST be run next before any implementation begins. No edits should be made to `/home/devuser/.claude/plugins/wills-plugins/plugins/wills-skills/commands/aws-sa/SKILL.md` until the Reviewer has issued its verdict on this plan.
