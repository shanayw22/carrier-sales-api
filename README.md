# carrier-sales-api

Submission-ready prototype for inbound carrier load sales automation on HappyRobot.

## Step 3: Run It

```bash
# Copy your loads.json into app/data/
cp /path/to/your/loads.json app/data/loads.json

# Start everything
docker-compose up --build

# Test health
curl http://localhost:8000/health

# Test carrier lookup (existing Lambda functionality)
curl -H "X-API-Key: YOUR_API_KEY" \
  "http://localhost:8000/carriers?mc_number=123456"

# Test load lookup (existing Lambda functionality)
curl -H "X-API-Key: YOUR_API_KEY" \
  http://localhost:8000/loads/LOAD-001

# Test webhook (new)
curl -X POST http://localhost:8000/webhook/call-complete \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "call_id": "test-001",
    "carrier_name": "Test Trucking LLC",
    "mc_number": "123456",
    "load_id": "LOAD-001",
    "outcome": "booked",
    "final_rate": 2500.00,
    "sentiment": "positive",
    "negotiation_rounds": 2
  }'

# Test metrics (new)
curl -H "X-API-Key: YOUR_API_KEY" \
  http://localhost:8000/metrics/summary

# Open the dashboard shell
open http://localhost:8000/dashboard/
```

## What You're Achieving

| Before (Lambda) | After (FastAPI + Docker) |
| --- | --- |
| `GET /carriers?mc_number=X` | `GET /carriers?mc_number=X` |
| `GET /loads/{id}` | `GET /loads/{id}` |
| - | `POST /webhook/call-complete` |
| - | `GET /metrics/summary` |
| - | `GET /metrics/calls` |

## Dashboard

The deployed API now serves a lightweight dashboard shell at `/dashboard/`.

Production URLs:

- API base: `https://api.hrsubs.dev`
- Dashboard: `https://api.hrsubs.dev/dashboard/`
- Health check: `https://api.hrsubs.dev/health`

- The page is public so a browser can load it.
- The page asks for your `X-API-Key` and then reads `/metrics/dashboard` and `/metrics/calls`.
- The webhook endpoint is idempotent by `call_id`, so workflow retries update the same record instead of creating duplicates.
- The dashboard includes a negotiation pressure scatter plot and a protected flush action that clears prior call metrics through `DELETE /metrics/flush`.

### Security Notes

- All API endpoints that expose business data require `X-API-Key` authentication.
- The dashboard shell itself is public so a browser can load the HTML, but the dashboard data requests still require the API key header.
- HTTPS is live at `https://api.hrsubs.dev`.
- Replace local example secrets with real environment-specific values before sharing the project externally.

### What The Dashboard Is For

The dashboard is the read side of the system.

- Your Happy Robot workflow posts completed call data into `POST /webhook/call-complete`.
- The API stores that payload in PostgreSQL.
- The dashboard reads the stored records back through `/metrics/dashboard` and `/metrics/calls`.

Use the dashboard to review:

- booking rate
- negotiation rounds
- call duration
- rate outcomes
- lane mix
- recent call records

It is not the thing that triggers the workflow. It is the reporting surface for the workflow output.

## Happy Robot Webhook

Use this endpoint in the post-call action or completed-call webhook step:

- URL: `https://api.hrsubs.dev/webhook/call-complete`
- Method: `POST`
- Headers:
  - `Content-Type: application/json`
  - `X-API-Key: <your API key>`

Recommended production note: rotate away from the current local dev key before sharing the system outside testing.

Example payload:

```json
{
  "call_id": "{{call.id}}",
  "caller_phone": "{{caller.phone}}",
  "carrier_name": "{{carrier.name}}",
  "mc_number": "{{carrier.mc_number}}",
  "dot_number": "{{carrier.dot_number}}",
  "allowed_to_operate": "{{carrier.allowed_to_operate}}",
  "load_id": "{{load.id}}",
  "origin": "{{load.origin}}",
  "destination": "{{load.destination}}",
  "equipment_type": "{{load.equipment_type}}",
  "offered_rate": {{negotiation.offered_rate}},
  "final_rate": {{negotiation.final_rate}},
  "loadboard_rate": {{load.loadboard_rate}},
  "outcome": "{{call.outcome}}",
  "sentiment": "{{call.sentiment}}",
  "negotiation_rounds": {{call.negotiation_rounds}},
  "call_duration_seconds": {{call.duration_seconds}},
  "timestamp": "{{call.completed_at}}"
}
```

Minimum useful fields if your workflow variables are limited:

```json
{
  "call_id": "{{call.id}}",
  "mc_number": "{{carrier.mc_number}}",
  "load_id": "{{load.id}}",
  "outcome": "{{call.outcome}}",
  "final_rate": {{negotiation.final_rate}},
  "sentiment": "{{call.sentiment}}",
  "negotiation_rounds": {{call.negotiation_rounds}},
  "call_duration_seconds": {{call.duration_seconds}}
}
```

The webhook is for writing data into the system. The dashboard is for reading and analyzing that stored data after calls complete.

## Submission Assets

- Prospect email draft: `PROSPECT_EMAIL_DRAFT.md`
- Broker-facing build description: `BROKER_BUILD_DESCRIPTION.md`
- Live dashboard: `https://api.hrsubs.dev/dashboard/`
- Live API: `https://api.hrsubs.dev`

## AWS Deploy

For ECS/Fargate deployment assets and commands, see [deploy/aws/README.md](deploy/aws/README.md).

## Reproducing Deployment

For cleaner reproduction documentation than the earlier manual AWS console walkthrough, use [deploy/aws/README.md](deploy/aws/README.md) together with the deployment templates in [deploy/aws](deploy/aws).

High-level reproduction flow:

1. Create the VPC networking, private/public subnets, NAT, and security groups in `us-east-2`.
2. Create the private RDS PostgreSQL instance and note the endpoint.
3. Store `API_KEY`, `FMCSA_API_KEY`, and `DATABASE_URL` in Secrets Manager.
4. Build and push the `linux/amd64` image to ECR.
5. Register the ECS task definition and force a new ECS deployment.
6. Verify `/health`, `/dashboard/`, and the protected API endpoints via the ALB DNS name.

## HTTPS On AWS

HTTPS is live on the ALB.

- Custom domain: `https://api.hrsubs.dev`
- HTTP `:80` redirects to HTTPS `:443`
- ACM certificate is attached to the ALB listener in `us-east-2`

Use HTTPS for all external integrations, including Happy Robot webhook calls and dashboard metric reads.