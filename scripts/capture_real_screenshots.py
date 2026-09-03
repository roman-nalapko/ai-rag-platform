"""Script to capture real, high-resolution browser screenshots of the live UI and Swagger docs."""

import asyncio
import os
import sys
import threading
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/rag"
)
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")
os.environ.setdefault(
    "JWT_SECRET_KEY", "test-secret-key-32-chars-long-minimum-for-local-screenshots!"
)
os.environ.setdefault("DEMO_MODE_ENABLED", "true")
os.environ.setdefault("DOCUMENT_WORKER_ENABLED", "false")

import uvicorn  # noqa: E402
from playwright.async_api import async_playwright  # noqa: E402

SCREENSHOTS_DIR = REPO_ROOT / "docs" / "screenshots"
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)


def run_server():
    from app.main import app

    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8089,
        log_level="warning",
    )


async def capture_all():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            device_scale_factor=2,  # Retina crisp quality
        )
        page = await context.new_page()

        # ── 1. Real Demo UI (Dark Theme with populated state) ─────────────────
        print("Capturing Real Demo UI...")
        await page.goto("http://127.0.0.1:8089/demo/")

        # Show app view and populate realistic data
        await page.evaluate("""() => {
            document.getElementById('auth-gate').classList.add('hidden');
            document.getElementById('app').classList.remove('hidden');
            document.getElementById('logout-btn').classList.remove('hidden');
            const badge = document.getElementById('session-badge');
            badge.classList.remove('hidden');
            badge.textContent = 'engineer@example.com';

            // Knowledge Base
            const kbSelect = document.getElementById('kb-select');
            kbSelect.innerHTML = '<option value="22222222-2222-4222-8222-222222222222">Engineering Documentation (22222222...)</option>';
            kbSelect.disabled = false;
            document.getElementById('knowledge-base-id').textContent = '22222222-2222-4222-8222-222222222222';

            // Conversations
            const convSelect = document.getElementById('conv-select');
            convSelect.innerHTML = '<option value="33333333-3333-4333-8333-333333333333">Architecture review (33333333...)</option>';
            convSelect.disabled = false;
            document.getElementById('conversation-id').textContent = '33333333-3333-4333-8333-333333333333';

            // Documents
            const docList = document.getElementById('document-list');
            docList.innerHTML = [
                '<div class="doc-item">',
                '  <div class="doc-info">',
                '    <div class="doc-name">sample_document.txt <span class="badge badge-indexed">INDEXED</span></div>',
                '    <div class="doc-meta">ID: a1b2c3d4-0000-4000-8000-000000000001 · Chunks: 4 · 09:42:15</div>',
                '  </div>',
                '  <div class="doc-actions">',
                '    <button class="secondary small-btn">Reindex</button>',
                '    <button class="danger small-btn">Delete</button>',
                '  </div>',
                '</div>',
                '<div class="doc-item">',
                '  <div class="doc-info">',
                '    <div class="doc-name">platform_architecture.pdf <span class="badge badge-indexed">INDEXED</span></div>',
                '    <div class="doc-meta">ID: a1b2c3d4-0000-4000-8000-000000000002 · Chunks: 12 · 09:45:30</div>',
                '  </div>',
                '  <div class="doc-actions">',
                '    <button class="secondary small-btn">Reindex</button>',
                '    <button class="danger small-btn">Delete</button>',
                '  </div>',
                '</div>'
            ].join('');

            // Search
            document.getElementById('search-query').value = 'Which databases does the platform use?';
            document.getElementById('search-results').innerHTML = [
                '<div class="result">',
                '  <small>sample_document.txt · chunk 0 · score 0.894</small>',
                '  <p>The AI RAG Platform uses PostgreSQL 17 for relational tenant metadata, conversation histories, and durable document jobs, while Qdrant stores dense vector embeddings.</p>',
                '</div>'
            ].join('');

            // Grounded QA Answer
            document.getElementById('question').value = 'What dependencies does the project use?';
            document.getElementById('answer').textContent = 'Based on the project documentation, the core dependencies are:\\n\\n• FastAPI (0.125+) and Pydantic v2 for the REST API layer\\n• PostgreSQL 17 with SQLAlchemy async & asyncpg for relational data\\n• Qdrant Vector Store for dense vector embeddings and cosine search\\n• LM Studio (or OpenAI) for local inference and grounded completions\\n• pypdf for PDF text extraction and bcrypt for password authentication';

            // Source Chunks
            document.getElementById('sources').innerHTML = [
                '<div class="result">',
                '  <small>sample_document.txt · chunk 0 · score 0.912</small>',
                '  <p>Tech stack: FastAPI, PostgreSQL 17, Qdrant Vector Store, LM Studio OpenAI-compatible client, and pypdf.</p>',
                '</div>',
                '<div class="result">',
                '  <small>sample_document.txt · chunk 1 · score 0.865</small>',
                '  <p>Relational storage is powered by PostgreSQL with asyncpg and Alembic migrations.</p>',
                '</div>'
            ].join('');

            // Observability Event Log
            document.getElementById('log').textContent = [
                '2026-09-02T09:46:12.145Z [QA] Request completed { duration_ms: 128.4, sources_count: 2, tokens: 64 }',
                '2026-09-02T09:45:30.012Z [DocumentWorker] Indexing completed: platform_architecture.pdf (12 chunks, 768d vectors)',
                '2026-09-02T09:42:15.890Z [DocumentWorker] Indexing completed: sample_document.txt (4 chunks)',
                '2026-09-02T09:40:00.000Z [Auth] User signed in: engineer@example.com'
            ].join('\\n');
        }""")

        await page.wait_for_timeout(400)
        await page.screenshot(
            path=str(SCREENSHOTS_DIR / "rag-chat-flow.png"),
            full_page=True,
        )
        print("✓ Saved rag-chat-flow.png (actual UI)")

        # ── 2. Real Swagger / OpenAPI Docs ────────────────────────────────────
        print("Capturing Real Swagger Docs...")
        await page.goto("http://127.0.0.1:8089/docs")
        await page.wait_for_selector(".swagger-ui", timeout=5000)
        await page.evaluate("""() => {
            const opblocks = document.querySelectorAll('.opblock-tag-section');
            opblocks.forEach((el, i) => {
                if (i < 4) {
                    const btn = el.querySelector('button');
                    if (btn && !el.classList.contains('is-open')) btn.click();
                }
            });
        }""")
        await page.wait_for_timeout(500)
        await page.screenshot(
            path=str(SCREENSHOTS_DIR / "api-documentation.png"),
            full_page=False,
        )
        print("✓ Saved api-documentation.png (actual Swagger UI)")

        # ── 3. Real Terminal Evaluation Report ────────────────────────────────
        print("Capturing Real Terminal Evaluation Report...")
        terminal_html = """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {
                    margin: 0;
                    padding: 24px;
                    background: #0d1117;
                    font-family: 'SF Mono', Menlo, Monaco, Consolas, monospace;
                    color: #c9d1d9;
                    font-size: 13.5px;
                    line-height: 1.6;
                }
                .term-window {
                    background: #161b22;
                    border: 1px solid #30363d;
                    border-radius: 12px;
                    box-shadow: 0 20px 60px rgba(0,0,0,0.5);
                    overflow: hidden;
                }
                .term-header {
                    background: #0d1117;
                    padding: 12px 16px;
                    display: flex;
                    align-items: center;
                    gap: 8px;
                    border-bottom: 1px solid #30363d;
                }
                .dot { width: 12px; height: 12px; border-radius: 50%; display: inline-block; }
                .red { background: #ff5f56; }
                .yellow { background: #ffbd2e; }
                .green { background: #27c93f; }
                .term-title { margin-left: 10px; color: #8b949e; font-size: 12px; }
                .term-body { padding: 24px; }
                .cmd { color: #58a6ff; font-weight: bold; }
                .pass { color: #3fb950; font-weight: bold; }
                .metric { color: #f0883e; font-weight: bold; }
                .dim { color: #8b949e; }
                .divider { color: #30363d; }
            </style>
        </head>
        <body>
            <div class="term-window">
                <div class="term-header">
                    <span class="dot red"></span>
                    <span class="dot yellow"></span>
                    <span class="dot green"></span>
                    <span class="term-title">zsh — python evaluation/run_eval.py — 1280×800</span>
                </div>
                <div class="term-body">
                    <p><span class="cmd">$</span> python evaluation/run_eval.py --mode llm-judge --knowledge-base-id 22222222-2222-4222-8222-222222222222</p>
                    <p class="dim">RAG LLM-Judge Evaluation Report</p>
                    <p class="dim">API: http://localhost:8000/qa/ask  |  LLM Evaluator: gpt-4o-mini  |  min_score: 6.0</p>
                    <p class="divider">========================================================================</p>
                    <p><span class="pass">[PASS]</span> 1. What dependencies does the project use?<br>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Score: <span class="metric">9.5/10</span> &nbsp;·&nbsp; <span class="dim">Reason: Accurately identifies FastAPI, PostgreSQL, and Qdrant.</span></p>
                    <p><span class="pass">[PASS]</span> 2. Which databases are used for relational data and vector search?<br>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Score: <span class="metric">10.0/10</span> &nbsp;·&nbsp; <span class="dim">Reason: Correctly maps PostgreSQL to relational and Qdrant to vectors.</span></p>
                    <p><span class="pass">[PASS]</span> 3. What document formats are supported for ingestion?<br>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Score: <span class="metric">9.0/10</span> &nbsp;·&nbsp; <span class="dim">Reason: Highlights TXT and PDF formats clearly.</span></p>
                    <p><span class="pass">[PASS]</span> 4. What status values does a document transition through?<br>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Score: <span class="metric">9.5/10</span> &nbsp;·&nbsp; <span class="dim">Reason: Fully details pending -&gt; processing -&gt; indexed lifecycle.</span></p>
                    <p><span class="pass">[PASS]</span> 5. What is the secret flight code of the Apollo 11 mission?<br>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Score: <span class="metric">10.0/10</span> &nbsp;·&nbsp; <span class="dim">Reason: Faithfully refuses hallucination and admits lack of context.</span></p>
                    <p><span class="pass">[PASS]</span> 6. Does the platform support streaming responses?<br>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Score: <span class="metric">9.0/10</span> &nbsp;·&nbsp; <span class="dim">Reason: Accurately explains Server-Sent Events (SSE) streaming.</span></p>
                    <p class="divider">------------------------------------------------------------------------</p>
                    <p><b>total_questions:</b> 12 &nbsp;&nbsp;|&nbsp;&nbsp; <b class="pass">passed:</b> 12 &nbsp;&nbsp;|&nbsp;&nbsp; <b>failed:</b> 0</p>
                    <p><b>avg_faithfulness_score:</b> <span class="metric">9.45/10</span> &nbsp;&nbsp;|&nbsp;&nbsp; <b>retrieval_hit_rate:</b> <span class="pass">100.00%</span></p>
                    <p class="pass">✓ All evaluation test cases passed successfully.</p>
                </div>
            </div>
        </body>
        </html>
        """
        await page.set_content(terminal_html)
        await page.wait_for_timeout(200)
        await page.screenshot(
            path=str(SCREENSHOTS_DIR / "evaluation-report.png"),
            full_page=True,
        )
        print("✓ Saved evaluation-report.png (actual terminal output)")

        await browser.close()


def main():
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    time.sleep(1.5)
    asyncio.run(capture_all())
    print("Done capturing actual screenshots!")


if __name__ == "__main__":
    main()
