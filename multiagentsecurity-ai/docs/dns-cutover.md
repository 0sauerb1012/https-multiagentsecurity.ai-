# DNS Cutover

## Current Assumption

The production domain is currently served elsewhere, and AWS should be validated before any cutover.

## Safe Validation Strategy

### 1. Test Without DNS Changes

- Deploy the web app to an Amplify-generated URL
- Use the Amplify URL for smoke testing and stakeholder review
- Confirm the web app can reach the intended backend and health endpoint

### 2. Optional Development Subdomain

- Create a non-production subdomain only after the app is stable
- Delegate just the required record rather than moving the whole zone
- Use this to test HTTPS, headers, and user-facing behavior in a more realistic setup

### 3. Prepare for Production

- Inventory current DNS records at HostGator
- Recreate required records in Route 53 only if full DNS migration is planned
- Reduce TTL for the production hostname before cutover

### 4. Cut Over Conservatively

- Update the specific production record to the AWS-managed target
- Validate the site, health endpoint, and cache behavior immediately
- Keep rollback instructions ready if traffic or content does not behave as expected

## What Not To Do Yet

- Do not move the apex domain to Route 53 just to start AWS testing
- Do not attach the production hostname before the backend and content paths are stable
- Do not assume Amplify provisioning needs to be fully automated before testing

## TODO

- Document the exact record changes once the final frontend hosting target is selected
- Add rollback runbook steps after the first dev or staging deployment is completed
