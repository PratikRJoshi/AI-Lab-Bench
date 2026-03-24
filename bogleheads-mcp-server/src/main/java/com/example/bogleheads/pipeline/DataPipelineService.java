package com.example.bogleheads.pipeline;

import com.example.bogleheads.mcp.model.ContextChunk;
import com.example.bogleheads.mcp.service.IndexService;
import com.example.bogleheads.parser.ParserService;
import com.example.bogleheads.scraper.ScraperService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.nio.file.Path;
import java.util.List;

/**
 * Orchestrates the end-to-end data pipeline: scraper -> parser -> indexer.
 */
@Service
public class DataPipelineService {
    private static final Logger log = LoggerFactory.getLogger(DataPipelineService.class);

    private final ScraperService scraperService;
    private final ParserService parserService;
    private final IndexService indexService;
    private final String rawDir;

    public DataPipelineService(
            ScraperService scraperService,
            ParserService parserService,
            IndexService indexService,
            @Value("${app.data.raw-dir}") String rawDir) {
        this.scraperService = scraperService;
        this.parserService = parserService;
        this.indexService = indexService;
        this.rawDir = rawDir;
    }

    /**
     * Run the full pipeline: crawl forums, download threads, parse, and index.
     *
     * @param pagesPerForum Number of topic pages to crawl per forum
     * @param pauseMs       Milliseconds to pause between HTTP requests
     */
    public void runFullPipeline(int pagesPerForum, long pauseMs) throws Exception {
        log.info("Starting full pipeline: pagesPerForum={}, pauseMs={}", pagesPerForum, pauseMs);

        // Step 1: Crawl forum index to discover thread URLs
        log.info("Step 1: Crawling forum index...");
        List<String> threadUrls = scraperService.crawlIndex(pagesPerForum);
        log.info("Discovered {} thread URLs", threadUrls.size());

        // Step 2: Download each thread's HTML
        log.info("Step 2: Downloading threads...");
        scraperService.downloadThreads(threadUrls, pauseMs);
        log.info("Download complete");

        // Step 3: Parse downloaded HTML into ContextChunks
        log.info("Step 3: Parsing HTML files...");
        List<ContextChunk> chunks = parserService.parseDirectory(Path.of(rawDir));
        log.info("Parsed {} context chunks", chunks.size());

        // Step 4: Bulk index all chunks
        log.info("Step 4: Indexing chunks...");
        indexService.indexChunks(chunks);
        log.info("Pipeline complete: indexed {} chunks", chunks.size());
    }

    /**
     * Re-index from existing HTML files on disk (skips scraping).
     */
    public void reindexFromDisk() throws Exception {
        log.info("Reindexing from disk: {}", rawDir);

        // Rebuild the index (clears existing data)
        indexService.rebuild();

        // Parse all HTML files
        List<ContextChunk> chunks = parserService.parseDirectory(Path.of(rawDir));
        log.info("Parsed {} context chunks from disk", chunks.size());

        // Bulk index
        indexService.indexChunks(chunks);
        log.info("Reindex complete: {} chunks", chunks.size());
    }
}
