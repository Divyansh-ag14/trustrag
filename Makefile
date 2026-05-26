.PHONY: setup dev infra backend frontend migrate seed eval test clean

# Start infrastructure services
infra:
	docker compose up -d

# Run database migrations
migrate:
	cd backend && .venv/bin/python -m alembic upgrade head

# Start backend dev server
backend:
	cd backend && .venv/bin/uvicorn app.main:app --port 8001 --reload

# Start frontend dev server
frontend:
	cd frontend && npm run dev

# Full dev setup (infra + migrate)
setup: infra
	@echo "Waiting for services..."
	@sleep 5
	$(MAKE) migrate
	@echo "Setup complete. Run 'make backend' and 'make frontend' in separate terminals."

# Start both backend and frontend (requires tmux or run separately)
dev:
	@echo "Run these in separate terminals:"
	@echo "  make backend"
	@echo "  make frontend"

# Load sample data and golden eval set
seed:
	cd backend && .venv/bin/python -m app.scripts.load_sample_data

# Trigger an evaluation run
eval:
	@TOKEN=$$(curl -s -X POST http://localhost:8001/api/v1/auth/login \
		-H "Content-Type: application/json" \
		-d '{"email":"test@gmail.com","password":"test@123"}' | \
		python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])") && \
	DATASET=$$(curl -s http://localhost:8001/api/v1/evaluation/datasets \
		-H "Authorization: Bearer $$TOKEN" | \
		python3 -c "import sys,json; d=json.load(sys.stdin); print(d[0]['id'])") && \
	curl -s -X POST http://localhost:8001/api/v1/evaluation/runs \
		-H "Authorization: Bearer $$TOKEN" \
		-H "Content-Type: application/json" \
		-d "{\"dataset_id\": \"$$DATASET\"}" | python3 -m json.tool

# Run tests
test:
	cd backend && .venv/bin/python -m pytest tests/ -v

# Stop infrastructure
clean:
	docker compose down
