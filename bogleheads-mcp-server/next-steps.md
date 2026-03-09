# Problem Statement
Build an MCP(Model Context Protocol) server for `bogleheads.org` forum. I want it to have readonly capability with full text search.

## TODO: MCP Server vs Chatbot Interaction

**Q:** Will I be able to interact with the final app here in the same way I can interact with ChatGPT or any other LLM?

**A:** The MCP server we are building is a **context-provider**, not an LLM.  You will query it over HTTP (e.g. `GET /v1/context?q=roth+conversion&limit=5`) and it will return JSON chunks (text + metadata) from bogleheads.org.  Those chunks are meant to be passed into an LLM prompt to give the model domain knowledge.  If you want a single endpoint that both retrieves context *and* generates answers, you can wrap the MCP server with another thin service that calls your chosen LLM (OpenAI, Claude, etc.) and streams the response back to the client.

> **Action item:** After the retrieval service is live, decide whether to add a chatbot wrapper or integrate directly with your existing LLM workflow.

## Roadmap

1. **Architecture / Tech Stack** 
   - Spring Boot 3.1
   - Lucene 10.2 (BM25)
   - Jsoup 1.17 for HTML parsing
   - Java 17 runtime
   - Local filesystem storage (raw HTML + JSON)

   **Action:** Create `architecture.md` with the following diagram so future contributors know how pieces fit together.

   ```text
                       +-------------------------------+
                       |  /v1/context?q=...&limit=N    |
                       |   REST Controller             |
                       +---------------+---------------+
                                       |
                       +---------------v---------------+
                       |  ContextService               |
                       |  (Lucene search + ranking)    |
                       +---------------+---------------+
                                       |
                       +---------------v---------------+
                       | Lucene Index (FSDirectory)    |
                       +---------------+---------------+
                                       ^
                       +---------------|---------------+
                       | ParserService |   HTML files  |
                       +---------------+---------------+
                                       ^
                       +---------------|---------------+
                       | ScraperService |  Raw threads |
                       +---------------+---------------+
                                       |
                       +---------------v---------------+
                       |  bogleheads.org               |
                       +-------------------------------+
   ```

2. **Scraper** (high priority)
   - Respect `robots.txt` → scrape only allowed paths.
   - Traverse forum index → discover thread URLs.
   - Handle pagination inside each thread.
   - Save each page’s raw HTML to `data/raw/YYYY/MM/DD/threadId_pageN.html`.

   *Sub-tasks*
   - (a) `ScraperService.crawlIndex()` ⇒ list of thread URLs.
   - (b) Fetch each URL and persist HTML.
   - (c) Unit-test on a couple short threads.

3. **Parser** (high priority)
   - Input: saved HTML file.
   - Output: `List<ContextChunk>` (id, topic, author, ts, text).
   - Chunk long posts if needed (e.g. 512 tokens max).

4. **Storage** (medium)
   - Abstract behind `StorageService` so we can swap in S3/DB later.

5. **Indexing** (high)
   - Switch to `FSDirectory` under `data/index`.
   - Wire `ParserService` → `IndexService` for incremental updates.
   - Rebuild index on startup if missing.

6. **API Endpoint** (high)
   - `GET /v1/context?q=&limit=` returns JSON array of chunks with `score`.

7. **Ranking** (medium)
   - Start with default BM25; later add recency/popularity boosts.

8. **Health Check** (low)
   - `GET /health` returns `{ "status": "UP" }`.

9. **Docker + CI + Deploy** (medium)
   - Dockerize app; GitHub Actions build/test; deploy to Cloud Run/Fly.io/Render.

## Progress Update (2025-09-10)

- Scraper implemented (crawl index + download HTML)
- Parser implemented (HTML → ContextChunk)
- Indexing switched to FSDirectory and persists across restarts
- REST API `/v1/context` live and returning results

## Upcoming Tasks

1. **Ranking improvements** (medium)
   - Tune BM25 parameters.
   - Add recency/popularity boost.
2. **Health-check endpoint** (low)
   - `GET /health` returns status + index size.
3. **Crawler orchestration** (medium)
   - Schedule periodic runs (Spring @Scheduled).
   - Skip unchanged threads by ETag/date.
4. **Dockerization** (medium)
   - Multi-stage build for slim JRE image.
5. **CI Pipeline** (medium)
   - GitHub Actions: mvn verify → docker build → push.
6. **Deployment** (low)
   - Use Cloud Run or Fly.io.

> **Next coding task:** create `/health` endpoint and simple rank tuning.
