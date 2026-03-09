package com.example.bogleheads.mcp.controller;

import com.example.bogleheads.mcp.model.ContextChunk;
import com.example.bogleheads.mcp.service.IndexService;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
public class ContextController {

    private final IndexService indexService;

    public ContextController(IndexService indexService) {
        this.indexService = indexService;
    }

    @GetMapping("/v1/context")
    public ResponseEntity<List<ContextChunk>> search(
            @RequestParam("q") String query,
            @RequestParam(value = "limit", defaultValue = "5") int limit) throws Exception {
        List<ContextChunk> results = indexService.search(query, limit);
        return ResponseEntity.ok(results);
    }
}
