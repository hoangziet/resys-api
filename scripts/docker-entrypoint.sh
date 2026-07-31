#!/usr/bin/env sh
set -eu

python -c "from core.database import init_db; init_db()"
python -m alembic upgrade head

exec "$@"
