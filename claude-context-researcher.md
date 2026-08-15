# Research Findings

## Source URLs
- [AWS Well-Architected Framework - Pillars](https://docs.aws.amazon.com/wellarchitected/latest/framework/the-pillars-of-the-framework.html)
- [AWS Well-Architected Framework - Operational Excellence Design Principles](https://docs.aws.amazon.com/wellarchitected/latest/framework/oe-design-principles.html)
- [AWS Well-Architected Framework - Security Design Principles](https://docs.aws.amazon.com/wellarchitected/latest/framework/sec-design.html)
- [AWS Well-Architected Framework - Reliability Design Principles](https://docs.aws.amazon.com/wellarchitected/latest/framework/rel-dp.html)
- [AWS Expands Well-Architected Framework with Responsible AI Lens - InfoQ](https://www.infoq.com/news/2025/12/aws-expands-well-architected/)
- [AWS Disaster Recovery Options in the Cloud](https://docs.aws.amazon.com/whitepapers/latest/disaster-recovery-workloads-on-aws/disaster-recovery-options-in-the-cloud.html)
- [AWS Service Portfolio Cull 2025 - InfoQ](https://www.infoq.com/news/2025/10/aws-service-portfolio-cull/)
- [AWS Control Tower Multi-Account Landing Zone](https://docs.aws.amazon.com/controltower/latest/userguide/aws-multi-account-landing-zone.html)
- [AWS Landing Zone Reference Architecture - Insighture](https://www.insighture.com/blogs/aws-landing-zone-reference-architecture)
- [AWS Solutions Architect Roles and Responsibilities - InterviewKickstart](https://interviewkickstart.com/blogs/articles/aws-solutions-architect-roles)
- [AWS Cost Optimization 2025 - Binadox](https://www.binadox.com/blog/aws-cost-optimization-2025-new-reserved-instance-strategies-and-savings-plans/)
- [AWS Account Vending with Control Tower - Wiz](https://www.wiz.io/blog/scaling-aws-account-management-from-landing-zones-to-account-vending)
- [AWS Savings Plans vs Reserved Instances - Finout](https://www.finout.io/blog/aws-savings-plans-vs-reserved-instances-5-key-differences-in-2025)
- [AWS Security Best Practices 2025 - SquareOps](https://squareops.com/knowledge/top-10-aws-security-best-practices-for-us-companies/)
- [Building AI Agents on AWS 2025 - DEV Community](https://dev.to/aws-builders/building-ai-agents-on-aws-in-2025-a-practitioners-guide-to-bedrock-agentcore-and-beyond-4efn)
- [AWS Networking Glossary - VPC Lattice, Transit Gateway, PrivateLink](https://hidekazu-konishi.com/entry/aws_networking_glossary.html)

---

## Core Concepts

### 1. AWS Well-Architected Framework — Six Pillars (Current as of 2025-2026)

The framework has six pillars. The Sustainability pillar was added in 2021 and is now fully established. At re:Invent 2025, AWS added a **Responsible AI Lens** and updated the ML and Generative AI Lenses, but the core six pillars are unchanged.

#### Operational Excellence
Design principles (verbatim from docs):
- Organize teams around business outcomes
- Implement observability for actionable insights
- Safely automate where possible
- Make frequent, small, reversible changes
- Refine operations procedures frequently
- Anticipate failure
- Learn from all operational events and metrics
- Use managed services

Key focus areas: CloudOps transformation, IaC-driven operations, CI/CD, runbooks-as-code, game days / chaos engineering.

#### Security
Design principles (verbatim from docs):
- Implement a strong identity foundation (least privilege, no long-term static credentials)
- Maintain traceability (real-time logging and alerting)
- Apply security at all layers (defence in depth)
- Automate security best practices (controls as code)
- Protect data in transit and at rest (classify by sensitivity; encryption, tokenisation, access control)
- Keep people away from data (reduce manual processing)
- Prepare for security events (incident response plans and simulations)

Current tooling emphasis: IAM Identity Center (SSO), AWS Organizations SCPs, GuardDuty + VPC Flow Logs + Lambda auto-remediation, Security Hub (aggregates GuardDuty, Inspector, Macie — near real-time risk analytics since Dec 2025), Inspector vulnerability scanning, Macie for S3 data classification, Config for drift detection.

Zero Trust: Assume no inherent trust; validate every request regardless of origin. Zero-trust VPCs with NACLs, security groups, and VPC endpoints to isolate workloads.

#### Reliability
Design principles (verbatim from docs):
- Automatically recover from failure (monitor KPIs, automate recovery)
- Test recovery procedures (validate in cloud using automation)
- Scale horizontally to increase aggregate workload availability
- Stop guessing capacity (monitor demand, automate scaling)
- Manage change through automation

Key tools: Route 53 health checks + Application Recovery Controller (ARC), AWS Resilience Hub (continuous RTO/RPO validation), Multi-AZ by default, Auto Scaling, AWS Fault Injection Simulator (FIS) for chaos engineering.

#### Performance Efficiency
Design principles:
- Democratize advanced technologies (use managed AI/ML services without deep expertise)
- Go global in minutes (multi-region deployments)
- Use serverless architectures
- Experiment more often
- Mechanical sympathy (understand how systems work, choose appropriate resource types)

Key areas: selection of right compute/database/storage, review as new services emerge, monitoring with CloudWatch/X-Ray, deliberate trade-offs (latency vs. cost vs. consistency).

#### Cost Optimization
Design principles:
- Implement Cloud Financial Management (FinOps practices)
- Adopt a consumption model (pay-per-use, avoid over-provisioning)
- Measure overall efficiency (business output vs. cost)
- Stop spending on undifferentiated heavy lifting (use managed services)
- Analyze and attribute expenditures (tagging strategy, per-team cost allocation)

2025 specifics: AWS now recommends **Savings Plans over Reserved Instances** for most compute workloads due to flexibility. AWS Database Savings Plan launched December 2025 covers RDS, Aurora, DynamoDB, ElastiCache, DocumentDB (up to 35% savings). Compute Savings Plans cover EC2, Fargate, Lambda (up to 66%). Standard RIs still preferred for highly stable, EC2-only baselines (up to 75% savings). FinOps Foundation targets ~80% commitment coverage for mature orgs; prefer 1-year over 3-year commitments given rapid technology shifts. Hybrid strategy: Savings Plans for variable/serverless + RIs for stable EC2 baseline + Spot for burst.

#### Sustainability
Design principles:
- Understand your impact (measure energy/carbon footprint)
- Establish sustainability goals
- Maximize utilization (rightsize; Graviton processors for efficiency)
- Anticipate and adopt more efficient hardware and software offerings
- Use managed services (AWS optimises underlying infra)
- Reduce downstream impact (minimise client-device compute requirements)

#### New Lenses (re:Invent 2025)
- **Responsible AI Lens**: 10 dimensions — controllability, privacy, security, safety, veracity, robustness, fairness, explainability, transparency, governance.
- **ML Lens** (updated): scalable ML workflows, bias mitigation.
- **Generative AI Lens** (updated): trustworthy AI design across the full AI lifecycle.

---

### 2. Key AWS Services by Domain

#### Compute
- **EC2**: Long-running, specific hardware/OS requirements, GPU workloads. Key: instance families (compute-optimised C-series, memory-optimised R/X-series, storage-optimised I-series, Graviton ARM-based for cost/performance). Placement groups for HPC. Nitro hypervisor for near-bare-metal performance.
- **Lambda**: Event-driven, short-duration (max 15 min), pay-per-invocation. Key: cold starts, concurrency limits (1,000 default soft limit per region), reserved vs. provisioned concurrency, Lambda SnapStart for Java. Layers for shared code.
- **ECS/EKS**: Containerised workloads. ECS simpler operational model; EKS for Kubernetes ecosystem. Fargate removes EC2 management. Know when Fargate vs. EC2 launch type.
- **AWS Batch**: Managed batch processing; uses EC2/Spot/Fargate.
- **Graviton**: ARM-based processors; up to 40% better price/performance than x86 equivalents. Should be default for new Lambda, ECS, RDS deployments.
- **App Runner**: Opinionated container deployment for simple web services; less control than ECS.

#### Networking
- **VPC**: Subnets (public/private/isolated), NACLs (stateless), Security Groups (stateful). CIDR planning is critical — cannot change VPC CIDR without recreation.
- **Transit Gateway (TGW)**: Hub-and-spoke for connecting many VPCs and on-premises. Replaces VPC peering at scale (peering does not support transitive routing). TGW route tables segment traffic.
- **PrivateLink**: Expose services privately across VPCs/accounts without internet traversal. Used for SaaS service access and cross-account service sharing. Works with TGW for hub-and-spoke PrivateLink distribution.
- **Direct Connect**: Dedicated private circuit to AWS; predictable latency, consistent bandwidth. Use with TGW for hybrid multi-VPC connectivity. MACsec for layer 2 encryption on Direct Connect.
- **Global Accelerator**: Static Anycast IPs; routes to closest healthy endpoint via AWS backbone. Advantage over Route 53: no DNS caching TTL delays for failover. Data plane failover (more resilient than Route 53 control plane for some scenarios).
- **Route 53**: DNS with health checks, latency/geolocation/geoproximity/weighted routing policies. Application Recovery Controller (ARC) for orchestrated failover using Route 53 as a data-plane switch.
- **CloudFront**: CDN with edge caching, Lambda@Edge and CloudFront Functions for edge logic. Origin shield reduces origin load. Use for static asset delivery, API acceleration, DDoS mitigation via AWS Shield.
- **VPC Lattice** (newer): Service-to-service connectivity within and across VPCs/accounts; simplifies the TGW + PrivateLink + Route 53 Resolver pattern for internal service mesh.

#### Storage
- **S3**: Object storage. Storage classes: Standard, Standard-IA, One Zone-IA, Glacier Instant Retrieval, Glacier Flexible Retrieval, Glacier Deep Archive, Intelligent-Tiering (auto-moves objects). S3 Lifecycle policies for transitions. S3 Replication (cross-region CRR, same-region SRR). Versioning + Object Lock (WORM) for compliance. S3 Express One Zone for ultra-low latency (single AZ, directory bucket).
- **EBS**: Block storage for EC2. gp3 (general purpose, baseline 3,000 IOPS, throughput configurable independently — cheaper than gp2), io2/io2 Block Express (provisioned IOPS SSD, multi-attach capable), st1 (throughput-optimised HDD for sequential big data), sc1 (cold HDD lowest cost). Snapshots to S3, cross-region copy.
- **EFS**: Managed NFS, multi-AZ, scales automatically. Performance modes: General Purpose vs. Max I/O. Throughput modes: Elastic (auto-scales), Bursting, Provisioned.
- **FSx family**: FSx for Windows File Server (SMB/AD integration), FSx for Lustre (HPC/ML, integrates with S3), FSx for NetApp ONTAP (multi-protocol, NFS/SMB/iSCSI), FSx for OpenZFS.
- **AWS Backup**: Centralised backup across EBS, RDS, DynamoDB, EFS, FSx, EC2, Storage Gateway. Cross-account and cross-region backup vault policies.
- **Storage Gateway**: Hybrid storage — File Gateway (NFS/SMB backed by S3), Volume Gateway (iSCSI backed by S3/EBS), Tape Gateway (virtual tape library backed by Glacier).

#### Databases
- **RDS**: Managed relational DB (MySQL, PostgreSQL, MariaDB, Oracle, SQL Server). Multi-AZ for HA (synchronous standby in different AZ). Read replicas for read scaling (up to 5 for most engines, 15 for Aurora). Automated backups, point-in-time restore. Proxy via RDS Proxy for connection pooling (critical for Lambda → RDS).
- **Aurora**: AWS-native MySQL/PostgreSQL compatible. Storage auto-scales to 128 TiB. Aurora Global Database: < 1s replication to secondary regions, < 1 min failover. Aurora Serverless v2: fine-grained autoscaling (0.5 ACU increments). Write forwarding from secondary to primary.
- **DynamoDB**: Serverless key-value/document store. On-demand or provisioned capacity. DAX for microsecond caching. Global Tables for multi-region active-active. Streams for change data capture. Design: single-table design, sparse indexes, know access patterns before designing schema.
- **ElastiCache**: Redis (persistence, pub/sub, Lua scripting, Global Datastore for cross-region) vs. Memcached (simple caching, multithreaded). Serverless ElastiCache (2024) auto-scales.
- **Redshift**: Columnar data warehouse. RA3 nodes with managed storage (Redshift Managed Storage). Redshift Serverless. Spectrum for querying S3. Data Sharing across clusters without copying.
- **Neptune**: Managed graph database (Gremlin / SPARQL / openCypher). Neptune Analytics for vector similarity search.
- **DocumentDB**: MongoDB-compatible managed document DB.
- **Keyspaces**: Managed Apache Cassandra-compatible.
- **Timestream**: Time-series database for IoT/operational metrics.
- **MemoryDB for Redis**: Redis-compatible but with durable, Multi-AZ in-memory database (durability via transaction log — different from ElastiCache Redis which is cache-first).

#### Serverless
- **Lambda**: See Compute section.
- **API Gateway**: REST API (v1, feature-rich), HTTP API (v2, lower latency/cost for simple proxies), WebSocket API. Usage plans + API keys for throttling. Lambda authorizers or Cognito authorizers.
- **Step Functions**: Serverless workflow orchestration. Standard (exactly-once, auditable, long-running) vs. Express (at-least-once, high-throughput, shorter). SDK integrations for 200+ AWS services.
- **EventBridge**: Serverless event bus. Default bus (AWS service events), custom buses (application events), partner buses (SaaS integrations). Event patterns for routing. EventBridge Pipes for point-to-point source-to-target with optional enrichment/filtering. EventBridge Scheduler for cron/rate scheduling (replaces CloudWatch Events rules for scheduling).
- **SQS**: Message queue. Standard (at-least-once, best-effort ordering) vs. FIFO (exactly-once, ordered, 3,000 msg/s with batching). DLQ for failed messages. Visibility timeout. Long polling to reduce API calls.
- **SNS**: Pub/sub fan-out. Topics with subscriptions (Lambda, SQS, HTTP, email, SMS, mobile push). FIFO topics for ordered fan-out.
- **Kinesis Data Streams**: Real-time streaming ingestion; shards define throughput (1 MB/s write, 2 MB/s read per shard). Enhanced fan-out for parallel consumers. Retention 24h default, up to 365 days.
- **Kinesis Data Firehose** (now Amazon Data Firehose): Managed delivery to S3, Redshift, OpenSearch, Splunk. Transform via Lambda. Near-real-time (60s or 1 MB buffer).
- **Bedrock**: Managed LLM/foundation model service. Access to Claude, Titan, Llama, Mistral, Stable Diffusion, etc. Knowledge Bases (RAG with vector stores). Agents (agentic loops, tool use). Guardrails for safety. AgentCore (2025) for production-ready autonomous agents. Secure via VPC endpoints and IAM.

#### Security (service layer)
- **IAM**: Users, Groups, Roles, Policies (identity-based, resource-based, permission boundaries, SCPs, session policies). IAM Identity Center (SSO) replaces legacy SSO; preferred for human access. IAM Access Analyzer for external access findings and policy validation. ABAC (attribute-based access control) via tags for scalable permission management.
- **KMS**: Customer managed keys (CMKs), AWS managed keys. Key policies + grants. Automatic key rotation. Multi-region keys. CloudHSM for dedicated HSM.
- **Secrets Manager**: Automatic rotation of database credentials, API keys. Reference secrets in ECS task definitions, Lambda env vars via dynamic references.
- **WAF**: Web ACL rules (managed rule groups from AWS + Marketplace). Rate-based rules. Attach to CloudFront, ALB, API Gateway, AppSync.
- **Shield**: Standard (free, automatic DDoS for L3/L4). Shield Advanced (enhanced DDoS, L7, 24/7 DRT, cost protection).
- **GuardDuty**: Threat detection from VPC Flow Logs, CloudTrail, DNS logs, S3 access logs, EKS audit logs, Lambda network activity. Findings in minutes.
- **Security Hub**: Aggregates findings from GuardDuty, Inspector, Macie, Config, IAM Access Analyzer. Evaluates against FSBP and CIS benchmarks.
- **Inspector**: Vulnerability scanning for EC2, ECR container images, Lambda.
- **Macie**: ML-powered sensitive data discovery in S3 (PII, financial data).
- **Config**: Configuration recording, compliance rules, conformance packs. Remediation via SSM Automation.
- **CloudTrail**: API activity logging (management events free at one trail; data events charged). Organisation trail for all accounts. Lake for SQL-based querying.
- **Certificate Manager (ACM)**: Free public TLS certs, auto-renewal. Private CA for internal services.

#### Observability
- **CloudWatch**: Metrics, Logs, Alarms, Dashboards. Metrics Insights for SQL-like metric queries. Log Insights for querying logs. Embedded Metrics Format (EMF) for Lambda custom metrics with zero latency. Contributor Insights for high-cardinality log analysis. Synthetics canaries for endpoint monitoring.
- **X-Ray**: Distributed tracing. Service maps. Sampling rules. Integrated with Lambda, API Gateway, ECS, ALB. Used with AWS Distro for OpenTelemetry (ADOT) for vendor-neutral instrumentation.
- **AWS Distro for OpenTelemetry (ADOT)**: OpenTelemetry SDK + AWS-specific exporters. The recommended path for new observability instrumentation (portable across clouds).
- **CloudWatch Application Signals**: Application performance monitoring (APM) built on OpenTelemetry; auto-instruments Java, Python, .NET. Provides SLO/SLI tracking natively.
- **Managed Grafana / Managed Prometheus**: For teams bringing their own observability stack.
- **CloudWatch Evidently**: Feature flagging and A/B experimentation.

---

### 3. Common Architecture Patterns

#### Multi-Region Strategies
- **Active-Active**: Traffic served from multiple regions simultaneously. DynamoDB Global Tables (write-local, last-writer-wins), Aurora Global Database (write-global, forwarding), S3 bidirectional replication. Route 53 latency-based or geoproximity routing, or Global Accelerator traffic dials. Near-zero RTO/RPO but highest complexity and cost.
- **Active-Passive (Hot Standby)**: Full replica of production in DR region, no traffic until failover. Highest cost among passive strategies but lowest RTO.
- **Warm Standby**: Scaled-down but fully functional copy always running in DR region. Can handle traffic immediately at reduced capacity; scale out on failover. Lower cost than hot standby, RTO of minutes.
- **Pilot Light**: Core data infrastructure (databases) running in DR region; application tier "switched off" (not deployed, or stopped). Must deploy/start application tier on failover. RTO of tens of minutes.
- **Backup and Restore**: Backups replicated to DR region; full rebuild on failover. Lowest cost, highest RTO/RPO. Suitable if DR scope is limited to data loss, not full regional outage.

Key principle: **prefer data plane operations for failover** (Route 53 health checks via ARC, Global Accelerator) over control plane operations (Auto Scaling, CloudFormation) for maximum resiliency during a disaster.

#### Disaster Recovery Services
- **AWS Resilience Hub**: Continuous RTO/RPO validation against targets; provides assessment scores.
- **AWS Elastic Disaster Recovery (DRS)**: Block-level continuous replication of EC2-hosted apps to AWS; pilot-light-based, automated failover.
- **Aurora Global Database**: < 1s cross-region replication latency, < 1 min managed failover.
- **DynamoDB Global Tables**: Multi-master, active-active, automatic conflict resolution (last-writer-wins).

#### Landing Zones (AWS Control Tower)
Structure:
- **Management (root) account**: AWS Organizations root; billing, SCPs, Control Tower. No workloads here.
- **Audit/Security account**: Centralised security tooling (Security Hub aggregation, GuardDuty delegated admin, Config aggregator, CloudTrail org trail).
- **Log Archive account**: Centralised, immutable CloudTrail and Config logs (S3 with Object Lock).
- **Shared Services account**: Centralised VPC (Transit Gateway), DNS (Route 53 Resolver), directory services, CI/CD tooling.
- **Workload accounts**: Per-team or per-environment (dev/staging/prod) isolated accounts. Accounts are the blast radius boundary.

Control Tower v4.0 (2025): Dedicated resources per service rather than shared resources. Auto-enrollment of accounts when moved into registered OUs. Account Factory for Terraform (AFT) for GitOps-driven account vending via Terraform. Drift detection and re-baselining built-in.

Account Vending best practice: accounts created natively in AWS Organizations → moved into registered OUs → Control Tower auto-enrolls and applies guardrails. AFT gives programmatic control via Terraform modules.

#### Event-Driven Architecture
- Decouple producers from consumers via SQS, SNS, EventBridge.
- Fan-out pattern: SNS → multiple SQS queues (each subscriber gets its own queue for independent processing).
- Saga pattern for distributed transactions: Step Functions orchestrator or choreography via events; compensating transactions on failure.
- CQRS + Event Sourcing: DynamoDB Streams → Lambda → read-optimised store (ElastiSearch/OpenSearch or separate DynamoDB table).

#### Microservices / Containerised Patterns
- EKS with Karpenter (node autoscaler, replaces Cluster Autoscaler) + KEDA for workload-based scaling.
- Service mesh: AWS App Mesh (Envoy-based) or VPC Lattice (newer, simpler, IAM auth-native).
- Sidecar pattern in ECS for log routing (FireLens with Fluent Bit).

#### Cost Optimisation Architecture Patterns
- **Spot Instance integration**: Use Auto Scaling Groups with mixed instance policies (On-Demand baseline + Spot for burst). Spot best for fault-tolerant, stateless, interruptible workloads.
- **Savings Plans over Reserved Instances**: Compute Savings Plans cover EC2+Fargate+Lambda; EC2 Instance Savings Plans for specific families; Database Savings Plans (Dec 2025) for RDS/Aurora/DynamoDB/ElastiCache/DocumentDB.
- **Graviton by default**: 20–40% cost reduction vs. x86 for same performance class.
- **S3 Intelligent-Tiering**: For unpredictable access patterns; no retrieval fees for frequent/infrequent tiers.
- **Lambda Power Tuning**: Find the optimal memory/CPU configuration; smaller is not always cheaper (faster execution = lower duration cost).
- **Non-production auto-shutdown**: Instance Scheduler or custom EventBridge Scheduler rules.
- **Tagging strategy**: Resource tagging enforcement via Config rules + SCPs; cost allocation tags for chargeback.

---

### 4. AWS Service Deprecations and Major Changes (2024–2025)

#### Deprecated / End-of-Life in 2024
- **AWS CodeCommit**: Closed to new customers (no hard shutdown date announced, but no new features). Migrate to GitHub, GitLab, or CodeCatalyst (also deprecated — see below).
- **AWS Cloud9**: Closed new customer access July 25, 2024. Alternatives: VS Code with AWS Toolkit, Cloud Shell, SageMaker Studio Code Editor.
- **AWS Snowmobile**: Silently deprecated early 2024.
- **AWS WorkDocs**: Stopped accepting new users April 24, 2024; data deletion April 26, 2025.
- **OpsWorks for Chef Automate**: EOL May 5, 2024.
- **OpsWorks Stacks**: EOL May 26, 2024. Migrate to Systems Manager, CodeDeploy, or Elastic Beanstalk.

#### Deprecated / Entering Maintenance or Sunset in 2025
AWS in 2025 adopted a batched lifecycle announcement approach (Maintenance / Sunset / End of Support classifications):

**Maintenance Phase** (new customers blocked November 7, 2025 — existing customers continue but no new features):
- Amazon Glacier (original vault-based API) — use S3 Glacier storage classes via S3 API instead
- Amazon S3 Object Lambda — evaluate if native S3 Transform features or Lambda + CloudFront can replace
- Amazon CodeCatalyst
- Amazon Cloud Directory
- Amazon CodeGuru Reviewer
- Amazon Fraud Detector
- .NET Modernization Tools
- AWS Mainframe Modernization Service
- AWS Systems Manager Change Manager
- AWS Systems Manager Incident Manager

**Sunset Phase** (full shutdown dates announced separately):
- Amazon FinSpace (launched 2021) — migrate to Amazon Redshift + Lake Formation
- Amazon Lookout for Equipment — migrate to Amazon Monitron or custom ML on SageMaker
- AWS IoT Greengrass v1 — migrate to Greengrass v2
- AWS Proton — new customer access closed October 7, 2025; full EOL October 7, 2026. Migrate to CDK Pipelines, Backstage, or internal platform tooling.

**Already EOL**:
- QLDB (Amazon Quantum Ledger Database): July 31, 2025. Migrate to Aurora PostgreSQL with ledger tables or DynamoDB with versioning.
- AWS Mainframe Modernization App Testing: October 7, 2025.

#### Major Service Changes / Launches (2024–2025) an SA Must Know
- **Amazon Bedrock GA + Agents + Knowledge Bases + Guardrails + AgentCore (2025)**: The primary GenAI platform. Replaces bespoke SageMaker LLM deployments for foundation model inference.
- **VPC Lattice GA (2023, now mature)**: Service-to-service networking across VPCs/accounts; IAM auth-based. Simplifies cross-VPC service discovery.
- **ElastiCache Serverless (2024)**: Auto-scales Redis/Memcached; per-request pricing.
- **Aurora Serverless v2 (GA 2022, widely adopted 2023–2025)**: Replaces v1 (deprecated). Fine-grained 0.5 ACU scaling increments, multi-AZ support, no cold starts at zero (minimum 0.5 ACU).
- **Lambda SnapStart for Java (GA 2022, mature)**: Dramatically reduces cold start; initialises snapshot at deploy time.
- **EventBridge Scheduler (GA 2022, now preferred)**: Replaces CloudWatch Events for scheduling; supports time zones, flexible recurring schedules, DLQ.
- **AWS Graviton3/3E/4**: Latest generation ARM chips; Graviton4 (r8g, c8g, m8g families) delivers ~30% better compute performance than Graviton3.
- **Amazon S3 Express One Zone (GA 2023)**: Single-AZ directory bucket with 10x lower latency and higher throughput for latency-sensitive apps.
- **AWS Control Tower v4.0 (2025)**: Per-service dedicated resources, auto-enrollment via OU registration.
- **AWS Database Savings Plan (December 2025)**: New commitment model covering 6 database services.
- **Amazon Security Hub updates (December 2025)**: Near real-time risk analytics, automated aggregation.
- **Amazon Application Recovery Controller (ARC)**: Mature feature for orchestrated multi-region failover using Route 53 as a data-plane switch.
- **AWS Resilience Hub**: Now the standard tool for validating and continuously tracking RTO/RPO targets.
- **Amazon CloudWatch Application Signals**: Native APM on OpenTelemetry; auto-instruments Java/Python/.NET; SLO/SLI dashboard.
- **Karpenter (1.0 GA, 2024)**: AWS-native Kubernetes node autoscaler; significantly outperforms Cluster Autoscaler; now recommended over CAS for EKS.
- **Amazon Q Developer** (formerly CodeWhisperer): AI coding assistant; integrated into IDEs and AWS console. An SA should be aware of how to govern its use (data residency, telemetry opt-out, professional tier for IP indemnification).

---

### 5. Senior SA vs. Junior SA: Distinguishing Characteristics

#### What a Junior SA does well
- Knows individual service capabilities and when to use each service
- Can implement reference architectures from AWS documentation
- Designs systems that work functionally
- Focuses on technical correctness within a defined scope
- Relies on prescriptive guidance (AWS Well-Architected Tool, reference architectures)

#### What distinguishes a Senior SA (the gap)

**Trade-off articulation over service knowledge**
A senior SA can articulate *why* a particular design choice was made by explicitly naming the trade-offs it accepts. Example: "We chose DynamoDB over Aurora here because we need sub-10ms P99 at 100k RPS globally and can enforce access patterns at the application layer. The trade-off is no ad-hoc query flexibility and harder schema evolution." They do not just say "DynamoDB is faster."

**Business context integration**
Senior SAs translate business requirements into architectural constraints before selecting services. They ask: What is the RTO/RPO the business will *actually* pay for? What is the regulatory scope (PCI, HIPAA, SOC 2, GDPR)? What is the team's operational maturity — can they operate a complex multi-region active-active topology? Cost envelope vs. availability SLA trade-offs are explicit, not implicit.

**Failure mode reasoning**
A senior SA designs for failure modes, not just the happy path. They explicitly consider: What happens when this SQS queue backs up? What is the blast radius of an IAM role compromise? What happens to the DynamoDB table when we hit a hot partition? How does the system behave during a partial AZ failure vs. a full regional outage?

**Control plane vs. data plane awareness**
Knowing that during a region-impacting event, control plane operations (Auto Scaling, CloudFormation, EC2 API calls to launch new instances) may be degraded before data planes are. Senior SAs design failover paths using data plane operations (Route 53 health checks via ARC, pre-provisioned warm standby capacity) rather than recovery paths that require control plane calls.

**Tenancy model and account strategy**
Knows how to structure AWS Organizations, OUs, and account boundaries based on blast radius, regulatory boundary, and team autonomy requirements. Not all workloads belong in one account; not all workloads need separate accounts. Can design the account vending strategy (AFT, Control Tower) and guardrail set (SCPs vs. Config rules vs. permission boundaries) appropriate to organisation maturity.

**Cost architecture as a first-class concern**
Senior SAs embed cost signals into architecture: choosing gp3 over gp2 by default (configurable throughput, lower cost), choosing Graviton over x86 as the default instance type, choosing Fargate Spot for non-critical batch ECS tasks, designing DynamoDB capacity mode (on-demand vs. provisioned) based on traffic predictability, and sizing Savings Plans commitments at time of architecture review not as an afterthought.

**Security by design, not bolt-on**
Considers the IAM permission model at design time (which role needs what, how are secrets rotated, is RDS Proxy needed to prevent credential sprawl). Knows when to use VPC endpoints vs. NAT Gateway (cost and security implications). Knows the difference between SCP (preventive, org-level) vs. Config rules (detective) vs. permission boundaries (delegation guardrails).

**Data gravity and latency awareness**
Understands that data movement across AZs costs money and adds latency; designs to keep compute co-located with data. Knows S3 Transfer Acceleration vs. CloudFront vs. Global Accelerator for different use cases. Understands Aurora read replica promotion vs. global database failover timing differences.

**Operational readiness**
Before declaring a design complete, a senior SA asks: How will the team deploy this? How will they roll back? How will they know when something is wrong (observability)? How will they respond to incidents (runbooks, on-call)? What is the patching strategy for EC2/EKS nodes? Is there a mechanism to test DR procedures (AWS FIS, Resilience Hub)?

**GenAI/AI workloads (2025-2026 addition)**
Senior SAs now need to know how to embed Bedrock into application architectures securely: VPC endpoint for Bedrock, IAM permission model for model access, Knowledge Base RAG pattern (chunking strategy, vector store choice — Aurora PostgreSQL pgvector vs. OpenSearch Serverless vs. Bedrock-native), Guardrails for content filtering, cost management for token-based pricing (caching, model selection), and when to fine-tune vs. prompt-engineer vs. RAG.

---

## Code Snippets

```hcl
# Terraform example: S3 bucket with recommended 2025 defaults
resource "aws_s3_bucket" "example" {
  bucket = "my-example-bucket"
}

resource "aws_s3_bucket_versioning" "example" {
  bucket = aws_s3_bucket.example.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "example" {
  bucket = aws_s3_bucket.example.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "aws:kms"
    }
    bucket_key_enabled = true  # Reduces KMS API calls and cost
  }
}

resource "aws_s3_bucket_public_access_block" "example" {
  bucket                  = aws_s3_bucket.example.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
```

```yaml
# CloudFormation: RDS Aurora Serverless v2 with Multi-AZ (recommended pattern)
AuroraCluster:
  Type: AWS::RDS::DBCluster
  Properties:
    Engine: aurora-postgresql
    EngineVersion: "16.2"
    DatabaseName: mydb
    MasterUsername: !Sub "{{resolve:secretsmanager:${DBSecret}:SecretString:username}}"
    MasterUserPassword: !Sub "{{resolve:secretsmanager:${DBSecret}:SecretString:password}}"
    ServerlessV2ScalingConfiguration:
      MinCapacity: 0.5
      MaxCapacity: 16
    StorageEncrypted: true
    DeletionProtection: true
    BackupRetentionPeriod: 7
    EnableCloudwatchLogsExports:
      - postgresql

AuroraPrimaryInstance:
  Type: AWS::RDS::DBInstance
  Properties:
    DBClusterIdentifier: !Ref AuroraCluster
    DBInstanceClass: db.serverless
    Engine: aurora-postgresql
    PubliclyAccessible: false

AuroraReplicaInstance:
  Type: AWS::RDS::DBInstance
  Properties:
    DBClusterIdentifier: !Ref AuroraCluster
    DBInstanceClass: db.serverless
    Engine: aurora-postgresql
    PubliclyAccessible: false
```

```python
# Lambda: Recommended pattern for RDS access via RDS Proxy
# - Uses IAM auth (no password in env vars)
# - Uses boto3 to generate auth token (rotates every 15 min)
import boto3
import psycopg2
import os

rds_client = boto3.client('rds')

def get_connection():
    token = rds_client.generate_db_auth_token(
        DBHostname=os.environ['DB_PROXY_ENDPOINT'],
        Port=5432,
        DBUsername=os.environ['DB_USER'],
        Region=os.environ['AWS_REGION']
    )
    return psycopg2.connect(
        host=os.environ['DB_PROXY_ENDPOINT'],
        port=5432,
        database=os.environ['DB_NAME'],
        user=os.environ['DB_USER'],
        password=token,
        sslmode='require'
    )

def handler(event, context):
    conn = get_connection()
    # ... query logic
    conn.close()
```

```json
// SCP example: Prevent disabling CloudTrail (preventive guardrail)
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "DenyCloudTrailDisable",
      "Effect": "Deny",
      "Action": [
        "cloudtrail:DeleteTrail",
        "cloudtrail:StopLogging",
        "cloudtrail:UpdateTrail"
      ],
      "Resource": "*"
    },
    {
      "Sid": "DenyLeaveOrganization",
      "Effect": "Deny",
      "Action": "organizations:LeaveOrganization",
      "Resource": "*"
    }
  ]
}
```

---

## Gotchas & Warnings

### Well-Architected Framework
- The framework has **six** pillars, not five. Sustainability was added in 2021 and is now fully established. Any SA giving 5 pillars is out of date.
- "Lenses" are separate from pillars. The Serverless Lens, SaaS Lens, Data Analytics Lens, and (new 2025) Responsible AI Lens extend the framework for specific domains. Conflating lenses with pillars is a common junior error.
- The Well-Architected Tool in the console lets you conduct formal reviews; AWS Partner Network partners conduct formal WA Reviews. A senior SA knows the process, not just the framework text.

### DR / Reliability
- **Control plane vs. data plane during regional events**: During a large-scale AWS event affecting a region, AWS control plane APIs (EC2 RunInstances, CloudFormation stack updates, Auto Scaling triggered scale-out) may be impaired before or alongside data plane degradation. Design failover to use pre-provisioned capacity (warm standby or hot standby) and data-plane routing (ARC + Route 53, Global Accelerator) rather than relying on launching new capacity during the event.
- **Aurora Serverless v2 minimum capacity**: The minimum is 0.5 ACU, not zero. It does not scale to zero (unlike v1 pause feature which had cold starts). For true scale-to-zero, use Aurora Serverless v1 (now deprecated in most engines) or a different pattern. Choose the minimum ACU appropriate to your response time requirements.
- **DynamoDB Global Tables write conflicts**: Last-writer-wins resolution. If two regions write to the same item concurrently, one write is silently discarded. Design schemas and access patterns to partition writes by region or use conditional writes with version attributes.
- **RTO/RPO testing**: Documenting targets is not the same as testing them. AWS Resilience Hub continuously validates. FIS can inject regional failure scenarios. A design that hasn't been tested is not a DR strategy — it's a DR hope.

### Networking
- **VPC CIDR cannot be changed**: Plan IP address space before deployment. RFC 1918 ranges (/16 per VPC is common). Overlapping CIDRs across VPCs prevent peering and TGW attachment. Use IPAM (AWS VPC IP Address Manager) for centralised planning.
- **VPC peering is not transitive**: VPC A peered with VPC B, VPC B peered with VPC C — A cannot reach C through B. Use Transit Gateway for transitive routing at scale.
- **Security Groups are stateful; NACLs are stateless**: NACL rules must be explicitly created for both inbound and return traffic. Common mistake: adding an inbound NACL allow rule without a corresponding outbound rule for ephemeral ports (1024–65535).
- **NAT Gateway cost**: Data processing charges (per GB) plus hourly charges. For high-throughput workloads, VPC Gateway Endpoints (S3, DynamoDB — free) and Interface Endpoints (PrivateLink) can eliminate significant NAT Gateway traffic. This is a cost and security win.

### Security
- **Long-term IAM access keys are an anti-pattern**: Use IAM roles everywhere — EC2 instance profiles, Lambda execution roles, ECS task roles. For human access, use IAM Identity Center. Access Analyzer detects external access to resources.
- **S3 bucket policies vs. ACLs**: ACLs are a legacy mechanism. AWS recommends disabling ACLs (Block Public Access + bucket policies only). Object Ownership should be set to "Bucket owner enforced."
- **KMS key deletion has a 7–30 day waiting period**: You cannot immediately delete a CMK. Plan key lifecycle and set key deletion alerts via EventBridge.
- **GuardDuty must be enabled in every region**: Threats in unused regions are still threats. Use AWS Organizations delegated admin to enable GuardDuty org-wide from the security account.

### Cost
- **gp2 vs. gp3**: gp3 is almost always cheaper and better. gp3 has a baseline of 3,000 IOPS and 125 MB/s throughput at no extra charge; gp2 ties IOPS to volume size (3 IOPS/GB). Many EBS volumes are still on gp2 and can be migrated with zero downtime via elastic volume modification.
- **Data transfer costs**: Intra-region cross-AZ data transfer is charged (~$0.01/GB each way). Design to minimise cross-AZ traffic for high-throughput systems (e.g., keep ELB in same AZ as targets where possible; use S3 VPC endpoints to avoid internet routing charges).
- **Savings Plans vs. RIs**: Savings Plans are more flexible (cover multiple instance families, Fargate, Lambda) and are now AWS's preferred commitment mechanism. Standard Reserved Instances lock to a specific instance type/region. Convertible RIs allow instance family changes but give lower discounts. For most new architectures, start with Compute Savings Plans.
- **Lambda cost model**: Charged on duration (GB-seconds) + invocations. More memory = faster execution = potentially lower cost. AWS Lambda Power Tuning tool (open source) finds the optimal memory setting empirically.

### Deprecations (Architect Should Not Recommend)
- Do not recommend CodeCommit for new source control implementations.
- Do not recommend Cloud9 as a development environment.
- Do not recommend OpsWorks (Chef or Puppet managed by AWS) — it is EOL.
- Do not recommend QLDB for new ledger/immutable audit log use cases — use Aurora PostgreSQL with ledger-pattern tables or DynamoDB with versioning.
- Do not recommend AWS Proton for new internal developer platform builds (EOL October 2026) — use Backstage, CDK Pipelines, or Terraform + GitHub Actions.
- Do not recommend Greengrass v1 for new IoT edge deployments — use Greengrass v2.
- Treat S3 Object Lambda and CodeCatalyst as maintenance-phase services: avoid for new workloads.

### GenAI / Bedrock
- **Bedrock is not a default VPC service**: By default, API calls go over the internet. Use VPC Interface Endpoint for Bedrock to keep traffic on the AWS network — required for most enterprise security postures.
- **RAG chunking strategy matters**: Poor chunking (too large = irrelevant context; too small = missing context) is the most common cause of RAG quality issues. Knowledge Bases support fixed-size, sentence-based, and hierarchical chunking (2024 addition).
- **Token costs accumulate in agentic loops**: Each tool call in a Bedrock Agent round-trips through the model. Design prompts to minimise unnecessary tool invocations; use Guardrails to reject clearly out-of-scope requests before they reach the model.
- **Model selection is an architecture decision**: Claude Haiku for low-latency high-volume classification; Claude Sonnet for complex reasoning; Claude Opus/largest models for highest quality with cost trade-off. This maps directly to the Performance Efficiency + Cost Optimization pillars.
