package com.example.bogleheads.mcp.controller;

import com.example.bogleheads.mcp.model.ContextChunk;
import com.example.bogleheads.mcp.service.IndexService;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

/**
 * Minimal MCP-compliant controller exposing /v1/context.
 * This is read-only and returns up to {@code limit} chunks that match the query.
 */
@RestController
public class McpController {

    private final IndexService indexService;

    public McpController(IndexService indexService) {
        this.indexService = indexService;
    }

    @GetMapping("/v1/context")
    public List<ContextChunk> context(@RequestParam("q") String query,
                                      @RequestParam(value = "limit", defaultValue = "10") int limit) throws Exception {
        return indexService.search(query, limit);
    }
}
