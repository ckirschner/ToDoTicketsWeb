#!/usr/bin/env bash
set -euo pipefail

# Reads .pi_sync.env and provides:
#  - ./sync_to_pi.sh               -> rsync project to the Pi
#  - ./sync_to_pi.sh --bootstrap   -> create venv, install deps on the Pi
#  - ./sync_to_pi.sh --install     -> pip install -r requirements.txt in venv
#  - ./sync_to_pi.sh --run         -> start uvicorn on the Pi (tmux session)
#  - ./sync_to_pi.sh --stop        -> stop the tmux session on the Pi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$ROOT_DIR/.pi_sync.env"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing $ENV_FILE. Create it first."
  exit 1
fi
# shellcheck disable=SC1090
source "$ENV_FILE"

PI_HOST="${PI_HOST:?PI_HOST not set in .pi_sync.env}"
PI_USER="${PI_USER:?PI_USER not set in .pi_sync.env}"
SSH_KEY="${SSH_KEY:?SSH_KEY not set in .pi_sync.env}"
PI_APP_DIR="${PI_APP_DIR:?PI_APP_DIR not set in .pi_sync.env}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
PI_VENV="${PI_VENV:-/home/pi/.venvs/todoticketsweb}"
UVICORN_PORT="${UVICORN_PORT:-8080}"
SSH_PORT="${PI_PORT:-22}"

# Expand tilde in SSH key path
SSH_KEY="${SSH_KEY/#\~/$HOME}"

# SSH connection string
SSH_CONN="$PI_USER@$PI_HOST"

APP_DIR_NAME="toDoTicketsWeb"
LOCAL_APP_PATH="$ROOT_DIR"

EXCLUDES=(
  "--exclude" ".git/"
  "--exclude" ".venv/"
  "--exclude" "__pycache__/"
  "--exclude" "*.pyc"
  "--exclude" "archives/"      # local archives; you can remove this if you want them synced
  "--exclude" "migrations/"
)

rsync_push() {
  echo "Syncing $APP_DIR_NAME -> $SSH_CONN:$PI_APP_DIR ..."
  rsync -az --delete "${EXCLUDES[@]}" \
    -e "ssh -i '$SSH_KEY' -p $SSH_PORT" \
    "$LOCAL_APP_PATH"/ \
    "$SSH_CONN:$PI_APP_DIR"/
  echo "Done."
}

remote() {
  ssh -i "$SSH_KEY" -p "$SSH_PORT" "$SSH_CONN" "$@"
}

bootstrap() {
  echo "Bootstrapping on $SSH_CONN ..."
  remote "mkdir -p '$PI_APP_DIR' && sudo apt-get update -y && \
    sudo apt-get install -y python3-venv python3-pip tmux \
      libcairo2 libpango-1.0-0 libgdk-pixbuf2.0-0 libffi8 libssl3 \
      fonts-dejavu-core && \
    mkdir -p '$(dirname "$PI_VENV")' && \
    test -d '$PI_VENV' || $PYTHON_BIN -m venv '$PI_VENV'"
  echo "Bootstrap complete."
}

install_deps() {
  echo "Installing Python deps in $PI_VENV ..."
  remote "source '$PI_VENV/bin/activate' && \
          pip install --upgrade pip && \
          pip install --no-input -r '$PI_APP_DIR/requirements.txt'"
  echo "Deps installed."
}

run_server() {
  # Runs the app in a tmux session named 'todotickets'
  echo "Starting server on $PI_HOST:$UVICORN_PORT ..."
  remote "tmux new-session -d -s todotickets \
    \"source '$PI_VENV/bin/activate' && \
     cd '$PI_APP_DIR' && \
     python -c 'from app.deps import init_db; init_db()' && \
     uvicorn app.main:app --host 0.0.0.0 --port $UVICORN_PORT --reload\" || true"
  echo "Server started. Open: http://$PI_HOST:$UVICORN_PORT"
}

stop_server() {
  echo "Stopping server tmux session ..."
  remote "tmux has-session -t todotickets 2>/dev/null && tmux kill-session -t todotickets || true"
  echo "Stopped."
}

usage() {
  cat <<EOF
Usage: $(basename "$0") [--bootstrap] [--install] [--run] [--stop] [--test]

No args: rsync project to Pi.

--bootstrap  Install system packages, create venv on the Pi
--install    Install Python deps from requirements.txt into the venv
--run        Start uvicorn in tmux on the Pi (port $UVICORN_PORT)
--stop       Stop uvicorn tmux session on the Pi
--test       Test SSH connection to the Pi
EOF
}

test_connection() {
  echo "Testing SSH connection to $SSH_CONN ..."
  if remote "echo 'Connection successful!'" 2>/dev/null; then
    echo "✅ SSH connection works!"
    remote "echo 'Pi hostname:' && hostname && echo 'Pi user:' && whoami && echo 'Pi date:' && date"
  else
    echo "❌ SSH connection failed!"
    echo "Check that:"
    echo "  - SSH key exists: $SSH_KEY"
    echo "  - Key is added to Pi: ssh-copy-id -i '$SSH_KEY' $SSH_CONN"
    echo "  - Pi is accessible: ping $PI_HOST"
    exit 1
  fi
}

case "${1:-}" in
  --bootstrap) bootstrap ;;
  --install)   install_deps ;;
  --run)       run_server ;;
  --stop)      stop_server ;;
  --test)      test_connection ;;
  "" )         rsync_push ;;
  *)           usage; exit 1 ;;
esac