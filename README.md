# Containerized Agentic AI Invoice Processing & Audit Platform

An AI-assisted invoice processing and audit application that extracts invoice data, translates non-English documents, checks invoice details against configurable rules and a mock ERP, and presents audit results for human review. It combines a LangGraph processing workflow with an invoice question-answering assistant, a Streamlit dashboard, and a Docker Compose service stack.

The application is intended as a development prototype. Its AI-generated fields, explanations, and recommendations should be reviewed by a person before they are used for business decisions.

## Capabilities

- **Automated document intake:** Watches the incoming invoice directory and starts processing supported PDF, DOCX, and PNG files. File checksums are used to detect duplicate submissions.
- **Text extraction and OCR:** Extracts PDF text and tables with `pdfplumber`, falls back to `pypdf`, and can OCR scanned PDFs and PNG images with Tesseract. DOCX paragraphs and tables are also supported.
- **Multilingual processing:** Uses an AWS Bedrock chat model to detect the document language and translate invoice text to English when needed, while instructing the model to preserve identifiers and numeric values.
- **Structured invoice extraction:** Uses the LLM to extract invoice headers and line items, identify missing required fields, summarize possible anomalies, and recommend `approve`, `manual_review`, or `reject`.
- **Data and business validation:** Applies configurable rules and compares invoice information with vendor, purchase-order, and SKU records exposed by the mock ERP service. Discrepancies and processing outcomes are persisted for audit.
- **Human review and feedback:** Provides invoice detail and audit pages for inspecting extracted data and discrepancies, recording field corrections, and revalidating invoices.
- **Invoice Q&A:** Routes questions to database queries or hybrid retrieval over indexed invoice reports. Retrieval combines Amazon Bedrock Titan embeddings in Qdrant with BM25 ranking. Generated answers can be evaluated with RAGAS relevance, groundedness, and context-relevance metrics.
- **Operations and reindexing:** Shows service health and audit statistics, and can rebuild the derived Qdrant index from invoice records in PostgreSQL.

## Processing workflow

1. Place an invoice file in `data/incoming`, which is mounted into the agent container as `/data/incoming`. Files in this directory are ignored by Git.
2. The background file watcher checks the file, computes its SHA-256 checksum, and records a pending audit entry. A previously processed file is treated as a duplicate.
3. The LangGraph invoice workflow extracts text, detects/translates the language, validates the extracted invoice fields, checks business data against the mock ERP, and generates a report.
4. The application stores invoice data, line items, discrepancies, processing status, and feedback in PostgreSQL. The generated invoice report is embedded and indexed in Qdrant for later retrieval.
5. Review the invoice and its recommendation in the Streamlit dashboard. Submit corrections from the Human Feedback page and revalidate when appropriate.
6. Ask natural-language questions from Invoice Q & A. Database-oriented questions are routed to the SQL workflow; document-oriented questions use hybrid retrieval and answer generation.

## Architecture

The stack runs as six Docker Compose services on the default Compose network:

| Service | Host port | Responsibility |
| --- | ---: | --- |
| `streamlit-ui` | `8501` | Dashboard, invoice review, feedback, Q&A, administration, and audit trail. |
| `agent` | `8000` | FastAPI endpoints and LangGraph workflows for invoice processing, RAG, feedback, revalidation, and index maintenance. |
| `mock-erp` | `8001` | Read-only vendor, purchase order, and SKU lookup API, seeded with local mock data. |
| `postgres` | `5432` | Persistent invoice audit data and mock ERP database. |
| `qdrant` | `6333` | Persistent vector index for invoice report retrieval; the index can be rebuilt from PostgreSQL. |
| `redis` | `6379` | Application cache and LangGraph server runtime support. |

### Technology

- Python 3.11
- Streamlit and FastAPI
- LangGraph, LangChain, and LiteLLM
- AWS Bedrock chat and Titan text-embedding models
- PostgreSQL, SQLAlchemy, Qdrant, and Redis
- `pdfplumber`, `pypdf`, `python-docx`, Pillow, Tesseract OCR, and Poppler
- Docker Compose

## Prerequisites

- Docker Engine with Docker Compose v2.
- AWS credentials with access to the configured Amazon Bedrock chat and embedding models in the selected region.
- A `LANGSMITH_API_KEY` for the LangGraph server.
- `langgraph-cli[inmem]` on the host if you need to regenerate the agent Dockerfile:

  ```bash
  python -m pip install "langgraph-cli[inmem]"
  ```

## Configuration

Create `agent/.env` before starting the stack. At minimum, provide the LangSmith key:

```dotenv
LANGSMITH_API_KEY=your-langsmith-api-key
```

Optional application settings can also be added there:

```dotenv
LITELLM_MODEL=bedrock/anthropic.claude-3-haiku-20240307-v1:0
EMBEDDING_MODEL=bedrock/amazon.titan-embed-text-v1
EMBEDDING_DIM=1536
```

The default chat and embedding model values are defined in the application. Ensure that the chosen model IDs are available to your AWS account and region. The current `compose.yaml` sets `AWS_REGION` to `us-east-1`; update that value in Compose when using another region. AWS authentication uses the AWS SDK credential chain. The current `compose.yaml` also mounts `/home/labuser/.aws` from the Docker host into the agent container; change that host-side path to your AWS credentials directory when running on a different machine. Do not commit credentials or populated `.env` files.

Compose-level database settings can be supplied through a root `.env` file:

| Variable | Default | Description |
| --- | --- | --- |
| `POSTGRES_USER` | `postgres` | PostgreSQL user. |
| `POSTGRES_PASSWORD` | `postgres` | PostgreSQL password; replace the development default before exposing the stack beyond a local environment. |
| `POSTGRES_DB` | `invoice_auditor` | Database name used by the services. |

`compose.yaml` sets service URLs and `AWS_REGION` for containers. The agent receives `DATABASE_URL`, `REDIS_URL`, `MOCK_ERP_URL`, and `QDRANT_URL`; the LangGraph runtime also receives `POSTGRES_URI` and `REDIS_URI`.

## Run locally with Docker Compose

From the project directory:

```bash
docker compose up --build -d
docker compose ps
```

Open the application and service endpoints:

- Streamlit application: <http://localhost:8501>
- Agent health endpoint: <http://localhost:8000/health>
- Agent API documentation: <http://localhost:8000/docs>
- Mock ERP API documentation: <http://localhost:8001/docs>
- Qdrant dashboard: <http://localhost:6333/dashboard>

Put supported invoices in `data/incoming`. Follow their processing status and recommendations in the dashboard. Use the Q&A page to ask questions about processed invoices.

View service logs:

```bash
docker compose logs -f agent
docker compose logs -f streamlit-ui
```

Stop the services while retaining persistent database and vector-store volumes:

```bash
docker compose down
```

Use `docker compose down -v` only when you intentionally want to delete the persistent PostgreSQL and Qdrant volumes.

## Regenerate the agent Dockerfile

Regenerate the Dockerfile when `agent/langgraph.json` changes in a way that affects dependencies, graph definitions, or Dockerfile instructions:

```bash
cd agent
langgraph dockerfile Dockerfile
cd ..
docker compose up --build -d
```

The generated Dockerfile uses the `langchain/langgraph-api:3.11` base image. Review generated changes before rebuilding.

## Repository layout

```text
agent/
  app/
    agents/       Extraction, translation, validation, reporting, and monitoring
    configs/      Validation rules and LLM personas
    db/           Database setup
    graph/        LangGraph processing, feedback, revalidation, and reindex graphs
    models/       Persistence models and request schemas
    rag/          Embedding, indexing, retrieval, SQL routing, and answer evaluation
    services/     Bedrock, ERP, and Redis integrations
mock_erp/         Read-only mock ERP API and seed data
streamlit_ui/     Streamlit dashboard and review pages
data/incoming/    Git-ignored invoice intake directory mounted into the agent
compose.yaml      Local multi-service development stack
```

## Operational notes

- PostgreSQL is the source of truth for invoice and audit data. Qdrant is a derived retrieval index and can be rebuilt from PostgreSQL using the Admin page.
- The LangGraph checkpoint tables may be created in PostgreSQL's default `public` schema rather than a separate `langgraph` schema. Application behavior does not depend on the checkpoint schema name.
- JSON and HTML reports are written to the agent container's local `reports/` directory and are not persisted across container recreation.
- The bundled ERP API is a local mock service, not a connection to a production ERP.
- The default PostgreSQL credentials and the mounted AWS credential path are for local development and must be adapted for your environment.
- The application has no authentication or authorization layer in this compose setup. Do not expose it or submit sensitive financial documents without adding appropriate access controls and reviewing your data-handling requirements.
