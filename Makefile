.PHONY: help install test lint format clean proto docker deploy

help:
	@echo "ShareServerless Makefile"
	@echo ""
	@echo "  install       Install all dependencies"
	@echo "  test          Run full test suite"
	@echo "  test-py       Run Python tests"
	@echo "  test-go       Run Go tests"
	@echo "  lint          Run linters"
	@echo "  format        Format all code"
	@echo "  proto         Generate protobuf stubs"
	@echo "  docker        Build all docker images"
	@echo "  clean         Clean build artifacts"

install:
	cd python && pip install -e ".[dev]"
	cd go && go mod download

test-py:
	cd python && pytest tests/ -v

test-go:
	cd go && go test ./...

test: test-py test-go

lint-py:
	cd python && ruff check . && mypy app/

lint-go:
	cd go && golangci-lint run

lint: lint-py lint-go

format:
	cd python && ruff format .
	cd go && gofmt -w .

proto:
	cd proto && buf generate || \
		protoc --go_out=../go/internal --go_opt=paths=source_relative \
		       --python_out=../python/app/proto \
		       *.proto || true

docker:
	docker compose -f docker/docker-compose.yml build

docker-up:
	docker compose -f docker/docker-compose.yml up -d

docker-down:
	docker compose -f docker/docker-compose.yml down

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name .pytest_cache -exec rm -rf {} +
	find . -type d -name .ruff_cache -exec rm -rf {} +
	rm -f python/.coverage
	find . -name '*.pyc' -delete
	cd go && go clean -cache
