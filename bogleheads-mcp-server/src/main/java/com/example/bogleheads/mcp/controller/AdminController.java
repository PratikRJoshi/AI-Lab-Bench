package com.example.bogleheads.mcp.controller;

import com.example.bogleheads.pipeline.DataPipelineService;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

/**
 * Admin endpoints for manual pipeline operations.
 */
@RestController
public class AdminController {

    private final DataPipelineService pipelineService;

    public AdminController(DataPipelineService pipelineService) {
        this.pipelineService = pipelineService;
    }

    @PostMapping("/admin/reindex")
    public ResponseEntity<Map<String, String>> reindex() {
        try {
            pipelineService.reindexFromDisk();
            return ResponseEntity.ok(Map.of("status", "success", "message", "Reindex complete"));
        } catch (Exception e) {
            return ResponseEntity.internalServerError()
                    .body(Map.of("status", "error", "message", e.getMessage()));
        }
    }
}
