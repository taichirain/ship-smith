#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

load_env() {
    if [ -f "${SCRIPT_DIR}/.env" ]; then
        echo "Loading environment from .env..."
        set -a
        while IFS= read -r line || [[ -n "$line" ]]; do
            [[ "$line" == \#* ]] && continue
            [[ -z "$line" ]] && continue
            export "$line"
        done < "${SCRIPT_DIR}/.env"
        set +a
    elif [ -f "${SCRIPT_DIR}/.env.example" ]; then
        echo "Loading environment from .env.example..."
        set -a
        while IFS= read -r line || [[ -n "$line" ]]; do
            [[ "$line" == \#* ]] && continue
            [[ -z "$line" ]] && continue
            export "$line"
        done < "${SCRIPT_DIR}/.env.example"
        set +a
    fi
}

show_help() {
    echo "ShipSmith Development Script"
    echo ""
    echo "Usage: $0 <command>"
    echo ""
    echo "Commands:"
    echo "  db-init           Create database and run migrations"
    echo "  db-reset          Drop and recreate database (DESTRUCTIVE)"
    echo "  start-api         Start FastAPI server (port 8000)"
    echo "  start-web         Start Next.js server (port 3000)"
    echo "  start-agent       Start Agent (requires AGENT_TOKEN env)"
    echo "  package-agent     Build agent binary with PyInstaller"
    echo "  all               Start API and Web in parallel"
    echo "  help              Show this help"
}

setup_python_env() {
    if [ ! -d "${SCRIPT_DIR}/.venv" ]; then
        echo "Creating virtual environment..."
        python3 -m venv "${SCRIPT_DIR}/.venv"
    fi
    source "${SCRIPT_DIR}/.venv/bin/activate"
}

load_env

case "${1:-help}" in
    db-init)
        echo "Setting up database..."
        setup_python_env
        pip install -e "${SCRIPT_DIR}/packages/config"
        pip install -e "${SCRIPT_DIR}/packages/db"
        pip install sqlalchemy alembic psycopg2-binary python-dotenv

        cd "${SCRIPT_DIR}/packages/db"
        alembic upgrade head
        echo "Database initialized!"
        ;;

    db-reset)
        read -p "This will DROP and RECREATE the database. Continue? (y/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            echo "Aborted."
            exit 0
        fi
        setup_python_env
        pip install -e "${SCRIPT_DIR}/packages/config"
        pip install -e "${SCRIPT_DIR}/packages/db"
        pip install sqlalchemy alembic psycopg2-binary python-dotenv

        cd "${SCRIPT_DIR}/packages/db"
        alembic downgrade base
        alembic upgrade head
        echo "Database reset complete!"
        ;;

    start-api)
        setup_python_env
        pip install -e "${SCRIPT_DIR}/packages/config"
        pip install -e "${SCRIPT_DIR}/packages/db"
        pip install -e "${SCRIPT_DIR}/apps/api"
        pip install fastapi uvicorn sqlalchemy alembic python-dotenv passlib pyjwt

        cd "${SCRIPT_DIR}/apps/api"
        export PYTHONPATH="${SCRIPT_DIR}/packages/config:${SCRIPT_DIR}/packages/db:${PYTHONPATH}"
        uvicorn shipsmith_api.main:app --host 0.0.0.0 --port 8000 --reload
        ;;

    start-web)
        cd "${SCRIPT_DIR}/apps/web"
        if [ ! -d "node_modules" ]; then
            npm install
        fi
        npm run dev
        ;;

    start-agent)
        if [ -z "${SHIPSMITH_AGENT_TOKEN}" ]; then
            echo "Error: SHIPSMITH_AGENT_TOKEN environment variable is required"
            exit 1
        fi
        if [ -z "${SHIPSMITH_WORKDIR}" ]; then
            echo "Error: SHIPSMITH_WORKDIR environment variable is required"
            exit 1
        fi

        setup_python_env
        pip install -e "${SCRIPT_DIR}/packages/config"
        pip install -e "${SCRIPT_DIR}/packages/db"
        pip install -e "${SCRIPT_DIR}/packages/agent"
        pip install httpx pydantic pyyaml python-dotenv psutil

        export PYTHONPATH="${SCRIPT_DIR}/packages/config:${SCRIPT_DIR}/packages/db:${SCRIPT_DIR}/packages/agent:${PYTHONPATH}"
        python3 -c "from shipsmith_agent.main import main; main()"
        ;;

    package-agent)
        cd "${SCRIPT_DIR}/packages/agent"
        bash package.sh "${2:-0.1.0}"
        ;;

    all)
        echo "Starting API and Web servers..."
        echo "API: http://localhost:8000"
        echo "Web: http://localhost:3000"
        echo ""
        echo "Press Ctrl+C to stop."
        echo ""

        setup_python_env
        pip install -e "${SCRIPT_DIR}/packages/config" > /dev/null 2>&1
        pip install -e "${SCRIPT_DIR}/packages/db" > /dev/null 2>&1
        pip install -e "${SCRIPT_DIR}/apps/api" > /dev/null 2>&1
        pip install fastapi uvicorn sqlalchemy alembic python-dotenv passlib pyjwt > /dev/null 2>&1

        export PYTHONPATH="${SCRIPT_DIR}/packages/config:${SCRIPT_DIR}/packages/db:${PYTHONPATH}"

        cd "${SCRIPT_DIR}/apps/api"
        uvicorn shipsmith_api.main:app --host 0.0.0.0 --port 8000 &
        API_PID=$!

        cd "${SCRIPT_DIR}/apps/web"
        if [ ! -d "node_modules" ]; then
            npm install
        fi
        npm run dev &
        WEB_PID=$!

        trap "echo 'Stopping...'; kill $API_PID $WEB_PID 2>/dev/null; exit" INT TERM

        wait $API_PID $WEB_PID
        ;;

    help|*)
        show_help
        ;;
esac
