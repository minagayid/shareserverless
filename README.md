# ShareServerless

> A decentralized compute, storage, and AI-hosting network.

Users contribute spare resources (CPU, GPU, RAM, Storage, Bandwidth, Availability) and get paid. Applications run at the edge without trusting any single provider.

**Philosophy:** Every workload may be malicious. Every node may be compromised. Every network connection may be hostile.

- Zero trust, mandatory sandboxing, signed workloads, least-privilege, multi-node verification, encryption by default.

## Layers

| # | Layer | Notes |
|---|-------|-------|
| 1 | Resource Discovery | Node registration, profiling, Tier 1–5 classification |
| 2 | Identity | Node ID + public key; no personal info required |
| 3 | Trust | Reputation engine (availability, accuracy, malicious reports, verifications) |
| 4 | Scheduling | Closest node, best reputation, lowest latency, available resources |
| 5 | Execution | Distributed execution, task segmentation (torrent-style chunking) |
| 6 | Verification | Multi-node consensus validation |
| 7 | Security | Container isolation (MicroVM/Firecracker), deny-by-default, signed workloads |
| 8 | Storage | Encrypted chunks, redundancy, self-healing |
| 9 | Networking | DDoS resistance, zero-trust |
| 10 | Governance | Contributors, validators, maintainers, auditors |

## Application Types

1. Static Websites
2. APIs
3. AI Inference (LLM hosts, embedding models, fine-tuning)

## Project Layout

```
shareserverless/
├── python/           # FastAPI scheduling/orchestration/governance
├── go/               # Node client, execution engine, networking, verification
├── proto/            # Protobuf/gRPC service definitions
├── docker/           # Dockerfiles & base images
├── deployments/      # K8s manifests, Terraform
├── monitoring/       # Prometheus, Grafana configs
└── web/              # Operator dashboard (optional)
```

## Quickstart

```bash
# Python API
cd python && pip install -e ".[dev]" && uvicorn app.main:app --reload

# Go node client
cd go && go run ./cmd/node

# Run all tests
make test
```

## License

MIT
