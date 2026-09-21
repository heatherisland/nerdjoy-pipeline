# Handoff: GTM Job-Search Engine — build in VS Code

This project is **designed and approved, not yet built.** You (the VS Code Claude session)
are picking it up to build it. Everything you need is here or linked.

## Mission

Build a public flagship: a fully-wired modern GTM data stack that runs Heather's job search
like a go-to-market pipeline, shown through one live interactive dashboard on real anonymized
funnel data, revealed in a single LinkedIn post. It must serve three goals at once —
attention, interview proof, and real outreach to target companies.

## Read first (in this order)

1. **The spec (authoritative):**
   `docs/superpowers/specs/2026-09-20-gtm-job-search-engine-design.md`
   — full architecture (§7), components (§8), build order (§10), risks (§11), testing (§12).
2. **Project rules:** `CLAUDE.md` (repo root) and `~/.claude/CLAUDE.md` (global).
3. Existing assets you will reuse: `scripts/harvest_sources.py`, `job_tracker.csv`,
   `.claude/commands/jobs/` (the `/jobs` flows: `find`, `outreach`, `daily`).

## Hard rules (non-negotiable — these are Heather's standing rules)

- **No em-dashes** (`—`) in ANY outgoing copy: LinkedIn post, dashboard hero, CTA,
  case-study cards. Scan every outgoing string before showing it; rewrite if found.
- **No PII / no names** in anything public or committed: `metrics.json`, the dashboard, the
  repo. Aggregates and generalized descriptors only. A deny-list grep guard (from the real
  tracker) must fail the build on any real name/domain hit.
- **`job_tracker.csv` is read-only** to the pipeline. Never mutate the source of truth.
- **You never enter credentials.** Heather does all OAuth/logins herself. You write the code
  and configs and guide her through each platform's auth.
- **Never commit** resume content, search profile, contacts, HubSpot exports, or account data.
- Outreach stays **human-in-the-loop**: DMs are confirmed by Heather before sending.

## Confirm these 4 decisions with Heather before building (defaults in bold)

1. Public brand name — **`nerdjoy // Pipeline`** · alts: `Funnel Me`, `Warm`.
2. Warehouse — **BigQuery on a billing-enabled project** (free-tier credits; NOT the sandbox,
   which Fivetran rejects). Snowflake trial is the fallback.
3. Hightouch second destination (the "today's warm-intro targets" list) — **Google Sheet**
   (vs Slack).
4. Public repo home — **`github.com/heatherisland`** (the profile she shares publicly) vs the
   `nerdjoyllc` org.

## Build order (from spec §10 — do NOT reorder; it protects trial windows)

1. Tracker → cloud Postgres (Neon/Supabase, NOT localhost); target companies → HubSpot (free).
2. dbt Core project against a seed/raw copy so marts can be built before Fivetran exists.
3. Dashboard shell reading a first `metrics.json` (tracker-fallback path, §8.7).
4. Hightouch syncs (free tier): BigQuery → HubSpot + Sheet/Slack.
5. **Fivetran connectors → BigQuery (wired late).** Postgres + HubSpot connectors only.
6. **Airflow/Astro DAG (wired late):** harvester → Fivetran sync → `dbt run`/`test` →
   Hightouch sync → refresh `metrics.json`.
7. Sanitize the public repo, capture proof screenshots/clips of every named tool's real run,
   write the reveal post.
8. Reveal.

**Trial protection:** Fivetran (~14-day trial) and Astro (paid after trial) are wired last;
capture proof of a real run immediately. Fallbacks if a trial lapses: Airbyte (Fivetran),
local `astro dev` (Astro).

## Access / preflight checklist (Heather provisions; you script around)

- [ ] Cloud Postgres (Neon or Supabase, free) — connection string.
- [ ] Google Cloud project with **billing enabled** + BigQuery API; service account JSON for dbt.
- [ ] HubSpot free CRM account + private-app token.
- [ ] Fivetran account (already signed up) — Postgres + HubSpot connectors; API key for Astro.
- [ ] Hightouch account (free) — BigQuery source; HubSpot + Sheet/Slack destinations; API key.
- [ ] Astronomer/Astro (trial) or local `astro dev`.
- [ ] Google Sheet (if chosen as the Hightouch destination).
- [ ] GitHub repo created under the chosen home (decision #4).

## The workflow to follow

This project was designed via the Superpowers brainstorming flow. Continue it:

1. Invoke the **writing-plans** skill to turn the spec into an ordered, buildable
   implementation plan. Get Heather's approval on the plan.
2. Then **executing-plans** with **test-driven-development** (TDD) for the code units
   (`metrics_extract.py` with its grep guard, dbt models with dbt tests, loaders).
3. Verify per spec §12 before the reveal.

## Definition of done (spec §14)

- Full stack runs end-to-end at least once, proof captured for every named tool.
- Public dashboard live: anonymized, em-dash-free, mobile-clean, light/dark.
- Reveal post drafted and ready.
- Heather can screen-share the dashboard + repo and trace any layer from source to
  activation without hand-waving.
