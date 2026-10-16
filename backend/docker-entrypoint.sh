#!/bin/sh
# Optional start-up steps, switched on by env vars, then exec the server (PID 1).
#   RUN_MIGRATIONS=true  -> alembic upgrade head
#   RUN_SEED=true        -> python -m app.seed (idempotent demo doctors/patients)
#   SEED_DEMO_QUEUE=true -> also fill today's queue with demo visits
set -eu

if [ "${RUN_MIGRATIONS:-false}" = "true" ]; then
  echo "entrypoint: running alembic upgrade head"
  alembic upgrade head
fi

if [ "${RUN_SEED:-false}" = "true" ]; then
  if [ "${SEED_DEMO_QUEUE:-false}" = "true" ]; then
    python -m app.seed --demo-queue
  else
    python -m app.seed
  fi
fi

exec "$@"
