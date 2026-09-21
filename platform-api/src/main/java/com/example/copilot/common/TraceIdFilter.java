package com.example.copilot.common;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.util.UUID;
import java.util.regex.Pattern;
import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

@Component
@Order(Ordered.HIGHEST_PRECEDENCE)
public class TraceIdFilter extends OncePerRequestFilter {

    private static final Pattern SAFE_LEGACY_TRACE_ID = Pattern.compile("[A-Za-z0-9_-]{16,64}");

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain filterChain)
            throws ServletException, IOException {
        var suppliedTraceparent = request.getHeader("traceparent");
        var traceId = TraceContext.traceIdFromTraceparent(suppliedTraceparent);
        if (traceId == null) {
            var legacy = request.getHeader("X-Trace-Id");
            traceId = legacy != null && SAFE_LEGACY_TRACE_ID.matcher(legacy).matches()
                    ? TraceContext.normalizeTraceId(legacy)
                    : UUID.randomUUID().toString().replace("-", "");
        }
        var serverTraceparent = TraceContext.childTraceparent(traceId, TraceContext.traceFlags(suppliedTraceparent));
        request.setAttribute(TraceContext.ATTRIBUTE, traceId);
        request.setAttribute(TraceContext.TRACEPARENT_ATTRIBUTE, serverTraceparent);
        response.setHeader("X-Trace-Id", traceId);
        response.setHeader("traceparent", serverTraceparent);
        filterChain.doFilter(request, response);
    }
}
