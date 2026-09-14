package com.example.copilot.common.api;

import java.time.Instant;
import java.util.Map;

public record ApiError(String code, String message, String traceId, Instant timestamp, Map<String, Object> details) {

    public static ApiError of(String code, String message, String traceId) {
        return new ApiError(code, message, traceId, Instant.now(), Map.of());
    }
}
