# AWS Postgres Cutover

This runbook moves the application database from Neon to an AWS-hosted PostgreSQL instance with minimal app changes.

## Scope

- keep the existing app code unchanged
- migrate data from Neon to Amazon RDS for PostgreSQL
- switch the runtime secret from the Neon `DATABASE_URL` to the AWS `DATABASE_URL`

## Preconditions

- Terraform has been applied with `managed_postgres_enabled = true`
- the RDS instance is available
- you know the new RDS endpoint, database name, username, and password
- you can pause ingestion during the final cutover window

## Important networking note

The ECS web service can reach a private RDS instance inside the same VPC without extra work.

The ingestion Lambda is different:

- if it stays outside the VPC, it cannot reach a private RDS instance
- if you attach it to the VPC, it loses direct internet egress unless you also add NAT

For that reason, cut over the web path first. Only move ingestion to the private database after deciding how Lambda internet egress will work.

## 1. Create the target connection string

Use the RDS values to form:

```text
postgresql://USERNAME:PASSWORD@RDS_ENDPOINT:5432/DB_NAME?sslmode=require
```

## 2. Pause scheduled ingestion

Disable or pause the EventBridge schedules before the final sync so data stops changing during cutover.

## 3. Export from Neon

Use PostgreSQL client tools from a workstation or CloudShell:

```bash
pg_dump \
  --format=custom \
  --no-owner \
  --no-privileges \
  --dbname "$NEON_DATABASE_URL" \
  --file neon.dump
```

AWS documents `pg_dump` and `pg_restore` as the standard path for PostgreSQL to RDS migrations, especially for moderate database sizes:

- https://docs.aws.amazon.com/en_us/dms/latest/sbs/chap-manageddatabases.postgresql-rds-postgresql-full-load-pd_dump.html
- https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/PostgreSQL.Procedural.Importing.html

## 4. Restore into RDS

```bash
pg_restore \
  --verbose \
  --clean \
  --if-exists \
  --no-owner \
  --no-privileges \
  --dbname "$AWS_DATABASE_URL" \
  neon.dump
```

## 5. Run a final delta sync if needed

If the source changed after the first dump, repeat the export and restore during the brief cutover window.

## 6. Update the AWS secret

Store the new AWS DSN in SSM Parameter Store at the same parameter name currently used for `DATABASE_URL`.

Example:

```bash
aws ssm put-parameter \
  --region us-east-1 \
  --name /multiagentsecurity/dev/DATABASE_URL \
  --type SecureString \
  --overwrite \
  --value 'postgresql://USERNAME:PASSWORD@RDS_ENDPOINT:5432/DB_NAME?sslmode=require'
```

## 7. Redeploy the web service

Force a new ECS deployment so the task reads the updated secret.

## 8. Smoke test

- load the site
- verify reads succeed
- create or update a record if you have a safe write path
- check CloudWatch logs for connection errors

## 9. Re-enable ingestion

Only re-enable ingestion after the database target is confirmed healthy.

If ingestion still runs on Lambda outside the VPC, it should continue using the old database until you solve private connectivity. Do not point it at a private RDS instance prematurely.
