# Deployment Plan

## Principle

Do not cut over the production domain until the AWS-hosted stack has been validated independently.

## Staged Rollout

### Phase 1: Frontend on Amplify Test URL

- Connect `apps/web` to AWS Amplify
- Deploy using the default Amplify branch URL
- Verify build, routing, API health, and environment variable wiring
- Keep DNS unchanged during this phase

### Phase 2: AWS Dev Environment

- Provision the dev database, ingestion Lambda, secrets, and schedule
- Point the web app at the dev data source
- Run ingestion against a constrained set of sources
- Validate schema, seed data, and basic page rendering

### Phase 3: Optional Dev Subdomain

- If desired, create a subdomain such as `dev.multiagentsecurity.ai`
- Route only after the Amplify-hosted app and backend stack are stable
- Keep production traffic on the existing HostGator-served site until confidence is high

### Phase 4: Staging and Production Readiness

- Add a staging environment for release verification
- Harden secrets handling, backups, monitoring, and CI checks
- Validate rollback procedures and database migration discipline

### Phase 5: Production Cutover

- Lower DNS TTL in advance
- Point the production domain to the validated frontend host
- Confirm health endpoint, core pages, and ingestion telemetry immediately after cutover

## Amplify Notes

Amplify is a pragmatic starting point for the web layer because it provides:

- Branch preview deployments
- Managed build and hosting
- Straightforward environment variable support
- A clean path to test URLs before any DNS change

Terraform support for Amplify can be added later, but documenting the process is sufficient for the current scaffold.
