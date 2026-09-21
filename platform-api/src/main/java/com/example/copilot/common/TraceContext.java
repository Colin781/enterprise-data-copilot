package com.example.copilot.common;

import jakarta.servlet.http.HttpServletRequest;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HexFormat;
import java.util.UUID;
import java.util.regex.Pattern;

public final class TraceContext {

    public static final String ATTRIBUTE = TraceContext.class.getName() + ".traceId";
    public static final String TRACEPARENT_ATTRIBUTE = TraceContext.class.getName() + ".traceparent";
    private static final Pattern TRACE_ID = Pattern.compile("[0-9a-f]{32}");
    private static final Pattern TRACEPARENT = Pattern.compile("00-([0-9a-f]{32})-([0-9a-f]{16})-([0-9a-f]{2})");

    private TraceContext() {}

    public static String current(HttpServletRequest request) {
        var value = request.getAttribute(ATTRIBUTE);
        return value instanceof String traceId ? traceId : "trace-unavailable";
    }

    public static String currentTraceparent(HttpServletRequest request) {
        var value = request.getAttribute(TRACEPARENT_ATTRIBUTE);
        return value instanceof String traceparent ? traceparent : childTraceparent(current(request));
    }

    public static String traceIdFromTraceparent(String value) {
        if (value == null) {
            return null;
        }
        var match = TRACEPARENT.matcher(value.toLowerCase());
        if (!match.matches() || isAllZero(match.group(1)) || isAllZero(match.group(2))) {
            return null;
        }
        return match.group(1);
    }

    public static String traceFlags(String value) {
        if (value == null) {
            return "01";
        }
        var match = TRACEPARENT.matcher(value.toLowerCase());
        return match.matches() ? match.group(3) : "01";
    }

    public static String normalizeTraceId(String value) {
        var normalized = value == null ? "" : value.toLowerCase();
        if (TRACE_ID.matcher(normalized).matches() && !isAllZero(normalized)) {
            return normalized;
        }
        return sha256(value == null ? "" : value).substring(0, 32);
    }

    public static String childTraceparent(String traceId) {
        return childTraceparent(traceId, "01");
    }

    public static String childTraceparent(String traceId, String flags) {
        return "00-" + normalizeTraceId(traceId) + "-" + randomSpanId() + "-" + flags;
    }

    private static String randomSpanId() {
        String spanId;
        do {
            spanId = UUID.randomUUID().toString().replace("-", "").substring(0, 16);
        } while (isAllZero(spanId));
        return spanId;
    }

    private static boolean isAllZero(String value) {
        return value.chars().allMatch(character -> character == '0');
    }

    private static String sha256(String value) {
        try {
            return HexFormat.of()
                    .formatHex(MessageDigest.getInstance("SHA-256").digest(value.getBytes(StandardCharsets.UTF_8)));
        } catch (NoSuchAlgorithmException exception) {
            throw new IllegalStateException("SHA-256 is unavailable", exception);
        }
    }
}
