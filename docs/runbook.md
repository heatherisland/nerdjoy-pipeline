# Runbook

Auth and setup steps that Claude never performs. Each one is for Heather.

## HUMAN STEP: HubSpot private app (Task 7)

1. Create a free HubSpot account at hubspot.com.
2. Settings > Integrations > Private Apps > Create a private app, named `nerdjoy-pipeline`.
3. Scopes: `crm.objects.companies.read`, `crm.objects.companies.write`.
4. Copy the access token into `.env` as `HUBSPOT_TOKEN`.
5. Settings > Properties > Companies: create four single-line text properties with the internal names `ats_platform`, `ats_slug`, `target_domain`, `stage_size`.
6. Run: `source .venv/bin/activate && python3 -m nerdjoy_pipeline.hubspot_loader`
7. Confirm the companies appear under CRM > Companies.
