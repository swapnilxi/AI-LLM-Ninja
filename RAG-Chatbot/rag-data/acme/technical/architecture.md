# Acme Platform Architecture

The Acme platform runs on three services: an API gateway (Node.js), an orders service (Python/FastAPI) and a
reporting service (Go). Data is stored in PostgreSQL 16; events flow through Kafka. Deployments use blue-green
releases every Tuesday at 10:00 UTC. The on-call rotation changes every Monday.
