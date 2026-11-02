# AWS Deployment Notes for Potion Paste

## Recommended minimal architecture

1. **Frontend**: S3 bucket (static website hosting disabled) + CloudFront distribution. Origin path = `/`. Cache static assets aggressively; set short TTL or use invalidation for `index.html` / `app.html` / `sw.js`.

2. **Backend compute**:
   - **Option A (simpler for pure REST)**: AWS Lambda + API Gateway HTTP API. Use Mangum or Zappa to adapt Flask. WebSockets via API Gateway WebSocket API (separate routes).
   - **Option B (better for Socket.IO)**: ECS Fargate service (1–2 tasks) running `gunicorn -k eventlet -w 1` or similar, behind an Application Load Balancer. Enable sticky sessions if needed. Put Redis (ElastiCache) as Socket.IO message queue when scaling >1 worker.

3. **Database**: Amazon RDS PostgreSQL (db.t4g.micro or small for start). Place in private subnet; security group allows only the compute security group on 5432.

4. **Secrets**: Secrets Manager secrets for `DATABASE_URL`, `SECRET_KEY`, optional OAuth keys. Inject as environment variables into Lambda / ECS task definition.

5. **Observability**: CloudWatch Logs for the compute service; basic alarms on 5xx and RDS CPU/storage.

6. **IAM**: Task / Lambda role with:
   - `secretsmanager:GetSecretValue` on the specific secret ARNs
   - (if S3 uploads later) `s3:PutObject` on a dedicated bucket
   - No broad `*` permissions

## Environment mapping

| Local | AWS |
|-------|-----|
| `DATABASE_URL` | RDS endpoint via Secrets Manager |
| `REDIS_URL` | ElastiCache (optional) |
| Static files | S3 + CloudFront |
| `SESSION_COOKIE_SECURE=True` | Always in production |
| CORS origins | CloudFront domain + custom domain |

## Deployment checklist

- [ ] RDS created, migrations run (`flask db upgrade` from a one-off task or bastion)
- [ ] Secrets populated
- [ ] Frontend built/copied to S3, CloudFront distribution live
- [ ] Backend service healthy, `/api/health` returns 200
- [ ] HTTPS only, HSTS optional
- [ ] Cookie domain / SameSite configured for your frontend origin
- [ ] CloudWatch alarms set
