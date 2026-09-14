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

    private static final Pattern SAFE_TRACE_ID = Pattern.compile("[A-Za-z0-9_-]{16,64}");

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain filterChain)
            throws ServletException, IOException {
        var supplied = request.getHeader("X-Trace-Id");
        var traceId = supplied != null && SAFE_TRACE_ID.matcher(supplied).matches()
                ? supplied
                : UUID.randomUUID().toString().replace("-", "");
        request.setAttribute(TraceContext.ATTRIBUTE, traceId);
        response.setHeader("X-Trace-Id", traceId);
        filterChain.doFilter(request, response);
    }
}
