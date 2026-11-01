
FROM langchain/langgraph-api:3.11

RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-eng \
    tesseract-ocr-spa \
    tesseract-ocr-deu \
    poppler-utils \
    libpq5 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -m -u 1000 -s /bin/bash appuser \
    && mkdir -p /deps/agent /api/langgraph_api /api/langgraph_runtime /api/langgraph_license /home/appuser/.aws /data/incoming /data/reports

WORKDIR /deps/agent

COPY --chown=appuser:appuser . /deps/agent

RUN for dep in /deps/*; do \
        echo "Installing $dep"; \
        if [ -d "$dep" ]; then \
            echo "Installing $dep"; \
            (cd "$dep" && PYTHONDONTWRITEBYTECODE=1 uv pip install --system --no-cache-dir -c /api/constraints.txt -e .); \
        fi; \
    done \
    && touch /api/langgraph_api/__init__.py /api/langgraph_runtime/__init__.py /api/langgraph_license/__init__.py \
    && PYTHONDONTWRITEBYTECODE=1 uv pip install --system --no-cache-dir --no-deps -e /api \
    && chown -R appuser:appuser /deps /api /home/appuser /data

RUN pip uninstall -y pip setuptools wheel \
    && rm -rf /usr/local/lib/python*/site-packages/pip* /usr/local/lib/python*/site-packages/setuptools* /usr/local/lib/python*/site-packages/wheel* \
    && find /usr/local/bin -name "pip*" -delete || true \
    && rm -rf /usr/lib/python*/site-packages/pip* /usr/lib/python*/site-packages/setuptools* /usr/lib/python*/site-packages/wheel* \
    && find /usr/bin -name "pip*" -delete || true \
    && uv pip uninstall --system pip setuptools wheel \
    && rm -f /usr/bin/uv /usr/bin/uvx

ENV HOME=/home/appuser \
    LANGGRAPH_HTTP='{"app": "/deps/agent/app/webapp.py:app"}' \
    LANGSERVE_GRAPHS='{"invoice_workflow": "/deps/agent/app/graph/workflow.py:graph", "rag": "/deps/agent/app/rag/rag_graph.py:graph", "revalidate": "/deps/agent/app/graph/revalidate.py:graph", "feedback": "/deps/agent/app/graph/feedback.py:graph", "reindex": "/deps/agent/app/graph/reindex.py:graph"}'

USER appuser
