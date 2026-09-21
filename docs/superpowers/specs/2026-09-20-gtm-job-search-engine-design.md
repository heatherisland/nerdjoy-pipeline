# Design: GTM Job-Search Engine (public flagship)

- **Date:** 2026-09-20
- **Owner:** Heather Barry
- **Status:** Draft for review
- **Working name (public brand TBD):** `nerdjoy // Pipeline` · alt: `Funnel Me` · `Warm`

## 1. Problem & goal

Heather is a senior data scientist / GTM engineer / martech-RevOps specialist running an
active job search. Applications alone are low-signal. She wants a single, clever build that
does three jobs at once:

1. **Attention** — a public, shareable artifact that pulls recruiters and hiring managers
   inbound.
2. **Proof** — a flagship she can screen-share in interviews that demonstrates real GTM /
   martech engineering depth instead of a story.
3. **Trojan horse** — the same engine runs real, tailored outreach at target companies.

**The idea:** her job search *is* a go-to-market motion (target companies = accounts,
hiring managers = leads, referrals = warm intros, outreach = sequencing, the tracker = a
CRM). She has already built most of the machinery. The build reframes it as a professional,
fully-wired modern GTM data stack, shows it through one interactive dashboard on real
anonymized funnel data, and narrates the engineering in public.

The one-line hook (the reveal post):
> "GTM Engineers get hired to wire up the revenue stack and automate the funnel. So I did
> exactly that, for my own job search. Here is the system, the integrations, and the
> pipeline data."

## 2. Non-goals (YAGNI)

- No public exposure of real company names, roles, or contacts (privacy model in §6).
- No multi-tenant product or sign-ups for v1. It is Heather's engine, shown publicly.
- No paid ad spend, no custom domain required for v1 (dashboard is a shareable hosted page).
- No net-new outreach automation beyond what already exists in `/jobs outreach`; we wire the
  existing flows into the stack, we do not rebuild them.

## 3. Audience

- **Primary:** GTM / RevOps / martech engineering hiring managers and recruiters on LinkedIn.
- **Secondary:** technical interviewers who will poke at the architecture and the repo.

Design implication: every named tool on the public diagram must be a tool actually wired
(the "honesty principle", §5). Aspirational tools are shown as a clearly separated roadmap
lane, or not at all.

## 4. Key decisions (locked)

| # | Decision | Choice |
|---|----------|--------|
| D1 | Emphasis | Balanced flagship: attention + proof + trojan horse together |
| D2 | Public data policy | Real aggregate metrics, no names; anonymized case studies |
| D3 | Sequencing | One big reveal. Full stack live before posting. ~2-3 weeks |
| D4 | Public centerpiece | One live interactive dashboard (hosted, shareable page) |
| D5 | Stack depth | Everything live: Fivetran, BigQuery, dbt, Hightouch, HubSpot, Airflow/Astro |
| D6 | Warehouse | BigQuery (billing-enabled project, free-tier credits; NOT the sandbox, which Fivetran rejects) |
| D7 | Source DB | Postgres (tracker) + HubSpot (companies/CRM) |
| D8 | Credentials | Heather enters all OAuth/logins herself; Claude never handles credentials |

## 5. The honesty principle

Every logo on the public architecture diagram is a tool genuinely wired at least once, with
a captured artifact (screenshot or short clip) proving a real run. This mirrors Heather's own
standing rule against padding a tool stack. Anything not truly wired is either omitted or
placed in a visually distinct "roadmap" lane labeled as such.

## 6. Data & privacy model

**Two layers, one direction of exposure:**

- **Private engine (real data):** Heather's real application/company data flows through her
  own accounts and platforms. This is her data in her tools; that is fine.
- **Public artifact (anonymized aggregates only):** the dashboard and the repo expose only
  aggregate metrics and anonymized case studies. Zero company names, person names, emails,
  or URLs.

**Guardrails (hard rules, from CLAUDE.md):**

- **No em-dashes** in any outgoing copy (LinkedIn post, dashboard hero text, CTA, case-study
  cards). Every outgoing string is scanned for `—` before Heather sees it and rewritten if
  found. (This internal spec is not outgoing copy.)
- **No PII / no names** in `metrics.json` or anything published or committed. A grep guard in
  the export step asserts the output contains none of the known company/contact strings.
- **Tracker is read-only** to the pipeline. The source of truth (`job_tracker.csv`) is never
  mutated by any build step.
- **Never commit** resume content, search profile, contacts, HubSpot exports, or account data
  to the public repo.

**Anonymization approach:** the metrics export reads real rows, computes aggregates
(counts, rates, time-series), and emits only numbers plus generalized descriptors
(e.g., "Series C, ~800 employees, martech" instead of a company name). Case studies are
hand-checked. A deny-list of real names/domains (sourced from the tracker) is grepped against
the final `metrics.json` and dashboard HTML; any hit fails the build.

## 7. Architecture

```
SOURCES              INGEST        WAREHOUSE      TRANSFORM       ACTIVATE           OUTBOUND
──────────────────────────────────────────────────────────────────────────────────────────────
ATS APIs             Fivetran  ──▶ BigQuery   ──▶ dbt         ──▶ Hightouch      ──▶ LinkedIn
 (Greenhouse/         connectors    (raw →         (marts:         (reverse           Gmail
  Lever/Ashby)                       marts)         funnel,         ETL)               HubSpot
 + HN "who's hiring"                                scoring)             │            (CRM of record)
Application tracker                       │                             │
 (Postgres)                               │                             │
HubSpot (CRM)  ───────────────────────────┘                             │
                                                                        │
             Airflow / Astro orchestrates the full run ─────────────────┘
             Claude + MCP agent ("/jobs daily") = AI control plane (reads marts, drafts outreach)
                                          │
                                          ▼
                                 Published dashboard  ◀── metrics.json (anonymized export)
```

*Note on the OUTBOUND column:* Hightouch feeds HubSpot and a Sheet/Slack only. LinkedIn and
Gmail outreach is driven by the agent reading those, not by Hightouch directly (§8.5, §9).

**The loop that sells it:** HubSpot holds companies/contacts/applications → Fivetran lands
HubSpot + ATS + tracker into BigQuery (raw) → dbt builds funnel and referral-scoring marts →
Hightouch syncs prioritized and "referral-needed" audiences back into HubSpot and the outbound
surface → Airflow runs it on a schedule → the agent reads the marts and drafts outreach.
Warehouse-in, warehouse-out. This is the exact shape of a real GTM/martech data stack.

## 8. Components & interfaces

Each unit has one purpose, a defined interface, and can be built and tested on its own.

1. **Source loaders**
   - Tracker → Postgres: a small loader that upserts `job_tracker.csv` rows into a Postgres
     table (read-only against the CSV; Postgres is a copy). **Postgres must be a
     cloud-reachable host (Neon or Supabase free tier), not localhost** — Fivetran is a cloud
     service and cannot reach a local database.
   - Target companies → HubSpot: companies from `resumes/target_companies.md` created as
     HubSpot companies (free CRM). Existing harvester output feeds this.
   - Interface: idempotent loaders; input = existing files, output = rows in Postgres/HubSpot.

2. **Fivetran connectors** (Postgres + HubSpot)
   - ATS/HN data is not synced by a bespoke ATS connector; the existing harvester writes ATS
     and "who's hiring" results into Postgres, and Fivetran's Postgres connector syncs that.
     So Fivetran's two real connectors are **Postgres** (tracker + harvested jobs) and
     **HubSpot** (companies/CRM).
   - Interface: configured in Fivetran UI (Heather auths), lands raw schemas in BigQuery.
   - Wired last in build order to protect the 14-day trial (§10).

3. **BigQuery** — raw + analytics datasets. Free sandbox.

4. **dbt Core project** (`dbt/`)
   - Models: `stg_applications`, `stg_companies`, `stg_jobs`, `fct_funnel`,
     `dim_company`, `mart_referral_scoring`, `mart_public_metrics` (anonymized).
   - Interface: `dbt run` produces marts in BigQuery; tested with dbt tests
     (not-null, accepted-values on status, referential).

5. **Hightouch syncs**
   - Sources: `mart_referral_scoring`, `fct_funnel`.
   - Destinations: HubSpot (audience/lead scoring), plus a Google Sheet or Slack for the
     "today's warm-intro targets" list. **Hightouch does not DM LinkedIn or send Gmail
     directly** — those stay agent-driven (§9): the agent reads the HubSpot audience / Sheet
     and drives the existing `/jobs outreach` LinkedIn + Gmail flows, human-in-the-loop.
   - Interface: models + syncs configured in Hightouch UI (Heather auths).

6. **Airflow / Astro DAG** (`dags/`)
   - Tasks: trigger harvester → trigger Fivetran sync (API) → `dbt run` → `dbt test` →
     trigger Hightouch sync → refresh `metrics.json`.
   - Interface: one scheduled DAG; local via `astro dev` (free) or Astro trial.

7. **Metrics export** (`scripts/metrics_extract.py`)
   - Input: `mart_public_metrics` in BigQuery (or the tracker directly as a fallback path).
   - Output: `metrics.json` — funnel counts by status, company/integration counts, outreach
     sent, referral conversion %, activity time-series. Anonymized by construction.
   - Includes the anonymization grep guard (§6).

8. **Dashboard** (published hosted page)
   - Consumes `metrics.json` (embedded inline at publish time). Presentation only.
   - Sections: hook → funnel viz → integration/architecture map (live lanes vs roadmap) →
     "how the agent works" → real metric tiles → 1-2 anonymized case-study cards → CTA.
   - Standards: phone-friendly, light/dark, nerdjoy palette, accessible.

9. **Public repo** (sanitized)
   - README with architecture diagram, integration list, the export script, dbt models,
     the DAG. No tracker data, no resume, no contacts.

10. **Reveal post** (LinkedIn)
    - Hook + 3-line story + dashboard link. Em-dash-scanned. First person.

## 9. Orchestration & the agent control plane

Airflow/Astro is the mechanical scheduler. The Claude + MCP agent (`/jobs daily`) is the
"decision" layer that reads the dbt marts, decides what to run next, and drafts outreach for
Heather to approve. In the narrative and the diagram this is the "AI control plane" sitting
above the data plane. DMs still require Heather's confirmation before sending (CLAUDE.md rule).

## 10. Build order & trial-window sequencing

Build order (nothing blocks downstream):

1. Tracker → Postgres; target companies → HubSpot.
2. dbt project scaffolded against a seed/raw copy so models can be built before Fivetran.
3. Dashboard shell reading a first `metrics.json` (from the tracker fallback path).
4. Hightouch syncs (free tier).
5. **Fivetran connectors → BigQuery (wired late).**
6. **Airflow/Astro DAG (wired late).**
7. Sanitize repo, capture proof clips, write the post, reveal.

**Trial protection:** Fivetran (~14-day trial, then paid/row-capped) and Astronomer/Astro
(paid after trial) are wired last, and a proof screenshot/clip of each real run is captured
immediately so nothing expires before the reveal. Honest fallbacks if a trial lapses:
Airbyte for Fivetran, local `astro dev` for Astro. BigQuery (free-tier credits on a
billing-enabled project), dbt Core, Hightouch free tier, and HubSpot free CRM carry no
trial window.

## 11. Risks & mitigations

| Risk | Mitigation |
|------|-----------|
| BigQuery sandbox rejected as Fivetran destination | Use a billing-enabled BigQuery project (free-tier credits cover the volume), not the pure sandbox; Snowflake trial is the fallback |
| Fivetran cannot reach local Postgres | Host the tracker Postgres on Neon/Supabase (free, cloud-reachable) |
| Hightouch free-tier limits (sync count, BigQuery source support) | Verify free-tier covers 2 syncs from BigQuery to HubSpot + Sheet before committing; keep the model count minimal |
| Trial expiry before reveal (Fivetran, Astro) | Wire late; capture proof immediately; fallbacks ready |
| Cost surprise | Only Fivetran/Astro can incur cost; cap usage, watch trial dates, downgrade to free fallbacks |
| Anonymization leak | Deny-list grep guard fails the build on any real name/domain hit |
| OAuth friction across 6 platforms | Heather drives auth; Claude scripts/config around it; sequence to isolate auth steps |
| "Self-referential = gimmicky" | Real stack + real metrics + honesty principle keep it credible, not cute |
| Scope creep past 3 weeks | Build order front-loads a shippable spine; later layers are additive |
| LinkedIn automation ToS | Outreach stays human-in-the-loop; DMs confirmed before send; no mass automation claims |
| Credential handling | Claude never enters credentials; Heather does, per D8 |

## 12. Testing & verification

- `metrics_extract.py`: output counts reconcile against a manual tracker sum; grep guard
  passes (no real names); schema of `metrics.json` validated.
- dbt: `dbt test` green (not-null, accepted status values, referential integrity).
- Pipeline: one full DAG run end-to-end produces fresh marts and a refreshed `metrics.json`.
- Dashboard: renders on mobile width, light and dark, all links resolve, no `—` present.
- Honesty audit: every logo on the diagram maps to a captured proof artifact.

## 13. Open decisions to confirm at review

- Public brand name: `nerdjoy // Pipeline` vs `Funnel Me` vs `Warm` vs other.
- Warehouse stays BigQuery (D6) unless Heather prefers Snowflake.
- Hightouch second destination: Google Sheet vs Slack for the "warm-intro targets" list.
- Repo home: `github.com/heatherisland` vs the `nerdjoyllc` org.

## 14. Success criteria

- The full stack runs end-to-end at least once, with proof captured for every named tool.
- The public dashboard is live, anonymized, em-dash-free, and mobile-clean.
- The reveal post is drafted and ready.
- In an interview, Heather can screen-share the dashboard and repo and trace any layer from
  source to activation without hand-waving.

---

*Next step after approval: create the implementation plan via the writing-plans skill.*
