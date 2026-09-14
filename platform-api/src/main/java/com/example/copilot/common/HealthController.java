package com.example.copilot.common;

import java.time.Instant;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class HealthController {

    @GetMapping("/health")
    public HealthResponse health() {
        return new HealthResponse("platform-api", "UP", Instant.now());
    }

    public record HealthResponse(String service, String status, Instant timestamp) {}
}
