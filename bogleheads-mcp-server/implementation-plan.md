# Plan: Bogleheads MCP Server — Full End-to-End Build

## Context

The project aims to be an MCP server for the Bogleheads.org forum but currently has **zero MCP protocol support** — it's just a REST API with a duplicate endpoint bug that prevents startup. The scraper, parser, and indexer exist but aren't wired together. This plan converts it into a real MCP server (with SSE transport for Claude Desktop) while keeping the REST API, and wires the data pipeline end-to-end.

---

## Phase 0: Save Plan to Project

**Goal:** Persist this plan as `implementation-plan.md` in the project root before any code changes.

- Create `/Users/pratik.joshi/Documents/Learning/Workshop/AI-Lab-Bench/bogleheads-mcp-server/implementation-plan.md` with the full contents of this plan

---

After creating `implementation-plan.md`, commit and push to remote:
```
git add implementation-plan.md
git commit -m "Add implementation plan for MCP server build"
git push origin main
```

---

## Phase 1: Fix Bugs & Clean Up

**Goal:** App compiles and starts without errors.

1. **Delete `McpController.java`** — duplicates `/v1/context` from `ContextController.java`, causing startup crash
   - `src/main/java/com/example/bogleheads/mcp/controller/McpController.java`

2. **Delete dead code** — Maven archetype leftovers
   - `src/main/java/com/example/App.java`
   - `src/test/java/com/example/AppTest.java`

3. **Create `src/main/resources/application.properties`**
   - `server.port=8080`, data dir paths, scraper toggle (`app.scraper.enabled=false`)

4. **Externalize hardcoded paths in `IndexService`**
   - Inject `app.data.index-dir` via `@Value` instead of hardcoding `"data/index"`
   - Add `Files.createDirectories()` in constructor to handle missing dir

**Verify:** `mvn clean compile && mvn spring-boot:run` starts on 8080. `GET /v1/context?q=test` returns `[]`.

---

## Phase 2: Wire Data Pipeline

**Goal:** Scraper → Parser → Indexer flows end-to-end. Lucene index contains real forum data.

1. **Add bulk indexing to `IndexService`**
   - New method `indexChunks(List<ContextChunk>)` — adds all docs, commits once (instead of per-doc commit)
   - File: `src/main/java/com/example/bogleheads/mcp/service/IndexService.java`

2. **Create `DataPipelineService`**
   - New file: `src/main/java/com/example/bogleheads/pipeline/DataPipelineService.java`
   - Injects `ScraperService`, `ParserService`, `IndexService`
   - `runFullPipeline()`: crawl → download → parse → bulk index
   - `reindexFromDisk()`: re-parse existing HTML files → rebuild index

3. **Create `PipelineRunner` (conditional startup)**
   - New file: `src/main/java/com/example/bogleheads/pipeline/PipelineRunner.java`
   - `CommandLineRunner` gated by `@ConditionalOnProperty("app.scraper.enabled")`
   - Disabled by default; set `app.scraper.enabled=true` to trigger on startup

**Verify:** Enable scraper, run app → HTML files appear in `data/raw/`, Lucene index populated. Disable scraper, restart → search returns results from persisted index.

---

## Phase 2.5: Fix Scraper 403 Forbidden

**Goal:** ScraperService successfully fetches pages from bogleheads.org without getting blocked.

**Root cause:** The scraper is trivially identifiable as a bot due to 3 issues:
1. User-Agent explicitly says "bogleheads-mcp/1.0" (bot signature)
2. No standard browser headers (Accept, Accept-Language, etc.)
3. No cookie persistence — each request is independent, session cookies are lost

**File:** `src/main/java/com/example/bogleheads/scraper/ScraperService.java`

**Changes:**

1. **Replace bot User-Agent with a realistic browser UA**
   - Use a current Chrome-on-macOS string: `Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36`

2. **Add standard browser headers to all requests**
   - `Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8`
   - `Accept-Language: en-US,en;q=0.5`
   - `Accept-Encoding: gzip, deflate`
   - `Connection: keep-alive`

3. **Implement cookie persistence across requests**
   - Maintain a shared `Map<String, String>` for cookies
   - On each response, merge `response.cookies()` into the shared map
   - Pass the shared map into every subsequent request via `.cookies(cookieMap)`
   - This ensures phpBB session cookies and any WAF cookies are preserved

4. **Add Referer header when navigating between pages**
   - When fetching a forum page, set Referer to the index URL
   - When fetching a thread page, set Referer to the forum page URL

5. **Add rate limiting to `crawlIndex()` inner loop**
   - Currently only `downloadThreads()` pauses between requests
   - Add `Thread.sleep(pauseMs)` between forum page fetches in the crawl loop

6. **Extract a helper method** for building Jsoup connections with all headers/cookies
   - Avoids repeating header setup in 3+ places
   - Something like `private Connection buildConnection(String url, String referer)`

**Verify:**
- Run with `app.scraper.enabled=true` and `app.scraper.pages-per-forum=1`
- Scraper fetches the forum index and at least some thread URLs without 403
- HTML files appear in `data/raw/YYYY/MM/DD/`
- If CloudFlare JS challenge is active (still 403), log a clear warning and fall back gracefully

**Limitation:** If bogleheads.org uses CloudFlare JavaScript challenges, Jsoup alone cannot solve them. In that case, a headless browser (Selenium/Playwright) would be needed — that's out of scope for this phase.

---

## Phase 3: Add MCP Protocol Support

**Goal:** Real MCP server with SSE transport. Claude Desktop can connect and use `search_forum` / `get_thread` tools.

1. **Upgrade Spring Boot 3.1.3 → 3.4.4** in `pom.xml`
   - Required by Spring AI MCP SDK (needs Spring Boot 3.4+)
   - Low risk — project uses minimal Spring features

2. **Add dependencies to `pom.xml`**
   - Spring AI BOM (`spring-ai-bom` 1.1.3)
   - `spring-ai-starter-mcp-server-webmvc` (provides SSE transport + `@Tool` annotations)

3. **Add MCP config to `application.properties`**
   - `spring.ai.mcp.server.name=bogleheads-mcp-server`
   - `spring.ai.mcp.server.version=1.0.0`

4. **Create MCP tool class**
   - New file: `src/main/java/com/example/bogleheads/mcp/tools/BogleheadsTools.java`
   - `@Tool search_forum(query, limit)` — searches Lucene, returns formatted post text
   - `@Tool get_thread(threadId)` — retrieves all posts from a thread by ID prefix

5. **Add `searchByThreadPrefix()` to `IndexService`**
   - Uses Lucene `PrefixQuery` on the `id` field for thread-level retrieval

6. **Rename REST endpoint** from `/v1/context` to `/api/v1/search` for clarity (MCP SSE lives at `/sse`)

**Verify:**
- `GET /api/v1/search?q=roth+conversion` returns JSON
- `GET /sse` responds (SSE endpoint)
- Configure Claude Desktop with `{"mcpServers":{"bogleheads":{"url":"http://localhost:8080/sse"}}}` → `search_forum` tool appears

---

## Phase 4: Health Check

**Goal:** Observable health endpoint with index status.

1. **Add `spring-boot-starter-actuator`** to `pom.xml`
2. **Expose health endpoint** in `application.properties` (`management.endpoints.web.exposure.include=health`)
3. **Create `IndexHealthIndicator`**
   - New file: `src/main/java/com/example/bogleheads/health/IndexHealthIndicator.java`
   - Reports UP/DOWN + document count from Lucene index

**Verify:** `GET /actuator/health` returns `{"status":"UP","components":{"index":{"details":{"docCount":N}}}}`

---

## Phase 5: Tests

1. **`IndexServiceTest`** — index + search with temp directory
2. **`ParserServiceTest`** — parse sample HTML fixture (`src/test/resources/sample-thread.html`)
3. **`BogleheadsToolsTest`** — integration test calling MCP tools against seeded index
4. **`ContextControllerTest`** — `@WebMvcTest` for REST endpoint with mocked `IndexService`

**Verify:** `mvn test` passes.

---

## Phase 6: End-to-End Validation with User Query

**Goal:** Prove the full system works by running a real query through both the REST API and MCP interface.

1. **Seed test data** (if scraper hasn't run yet)
   - Run `DataPipelineService.reindexFromDisk()` or enable scraper for a small crawl (1 page per forum)
   - Confirm Lucene index has documents via `/actuator/health`

2. **REST API validation**
   - Prompt the user for a sample query (e.g., "Roth conversion", "three fund portfolio", "bond tent")
   - Execute: `curl http://localhost:8080/api/v1/search?q=<user-query>&limit=3`
   - Verify: JSON response with relevant forum posts, non-empty `text` and `sourceUrl` fields

3. **MCP client validation (Claude Desktop / Cursor)**
   - Add to Claude Desktop config (`~/Library/Application Support/Claude/claude_desktop_config.json`):
     ```json
     {
       "mcpServers": {
         "bogleheads": {
           "url": "http://localhost:8080/sse"
         }
       }
     }
     ```
   - Restart Claude Desktop → verify `search_forum` and `get_thread` tools appear in the tool list
   - Ask Claude: "Search the Bogleheads forum for <user-query>" → Claude calls `search_forum` → returns forum posts
   - Ask Claude: "Get thread <threadId>" using an ID from the search results → Claude calls `get_thread`

4. **Cursor IDE validation** (alternative)
   - Add MCP server in Cursor settings → same SSE URL `http://localhost:8080/sse`
   - Verify tools appear and respond to queries

**This is the "it works" moment** — a user types a natural language question, Claude/Cursor calls the MCP tool, and forum knowledge comes back.

---

## Files Summary

| Action | File |
|--------|------|
| DELETE | `src/main/java/com/example/App.java` |
| DELETE | `src/main/java/com/example/bogleheads/mcp/controller/McpController.java` |
| DELETE | `src/test/java/com/example/AppTest.java` |
| MODIFY | `pom.xml` (upgrade Boot, add Spring AI + Actuator) |
| MODIFY | `IndexService.java` (externalize path, bulk index, prefix search) |
| MODIFY | `ContextController.java` (rename endpoint to `/api/v1/search`) |
| CREATE | `src/main/resources/application.properties` |
| CREATE | `src/main/java/.../pipeline/DataPipelineService.java` |
| CREATE | `src/main/java/.../pipeline/PipelineRunner.java` |
| CREATE | `src/main/java/.../mcp/tools/BogleheadsTools.java` |
| CREATE | `src/main/java/.../health/IndexHealthIndicator.java` |
| CREATE | 4 test files + 1 test resource |
