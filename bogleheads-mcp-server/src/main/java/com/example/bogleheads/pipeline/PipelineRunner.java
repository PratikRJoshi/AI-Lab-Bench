package com.example.bogleheads.pipeline;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.CommandLineRunner;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Component;

/**
 * Optional startup runner that executes the data pipeline on application boot.
 * Disabled by default (app.scraper.enabled=false).
 */
@Component
@ConditionalOnProperty(name = "app.scraper.enabled", havingValue = "true")
public class PipelineRunner implements CommandLineRunner {
    private static final Logger log = LoggerFactory.getLogger(PipelineRunner.class);

    private final DataPipelineService pipelineService;
    private final int pagesPerForum;
    private final long pauseMs;

    public PipelineRunner(
            DataPipelineService pipelineService,
            @Value("${app.scraper.pages-per-forum}") int pagesPerForum,
            @Value("${app.scraper.pause-ms}") long pauseMs) {
        this.pipelineService = pipelineService;
        this.pagesPerForum = pagesPerForum;
        this.pauseMs = pauseMs;
    }

    @Override
    public void run(String... args) throws Exception {
        log.info("PipelineRunner triggered - running full pipeline");
        pipelineService.runFullPipeline(pagesPerForum, pauseMs);
    }
}
