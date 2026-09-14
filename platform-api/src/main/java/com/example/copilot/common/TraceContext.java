package com.example.copilot.common;

import jakarta.servlet.http.HttpServletRequest;

public final class TraceContext {

    public static final String ATTRIBUTE = TraceContext.class.getName() + ".traceId";

    private TraceContext() {}

    public static String current(HttpServletRequest request) {
        var value = request.getAttribute(ATTRIBUTE);
        return value instanceof String traceId ? traceId : "trace-unavailable";
    }
}
