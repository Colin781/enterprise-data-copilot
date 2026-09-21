package com.example.copilot.common;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.regex.Pattern;
import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockFilterChain;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpServletResponse;

class TraceIdFilterTest {

    private static final Pattern TRACEPARENT = Pattern.compile("00-[0-9a-f]{32}-[0-9a-f]{16}-[0-9a-f]{2}");
    private final TraceIdFilter filter = new TraceIdFilter();

    @Test
    void preservesAnIncomingW3cTraceIdAndCreatesANewServerSpan() throws Exception {
        var traceId = "0123456789abcdef0123456789abcdef";
        var incoming = "00-" + traceId + "-1111111111111111-01";
        var request = new MockHttpServletRequest("GET", "/health");
        request.addHeader("traceparent", incoming);
        var response = new MockHttpServletResponse();

        filter.doFilter(request, response, new MockFilterChain());

        assertThat(request.getAttribute(TraceContext.ATTRIBUTE)).isEqualTo(traceId);
        assertThat(response.getHeader("X-Trace-Id")).isEqualTo(traceId);
        assertThat(response.getHeader("traceparent"))
                .matches(TRACEPARENT)
                .isNotEqualTo(incoming)
                .startsWith("00-" + traceId + "-");
    }

    @Test
    void rejectsAllZeroTraceIdsAndGeneratesAValidContext() throws Exception {
        var request = new MockHttpServletRequest("GET", "/health");
        request.addHeader("traceparent", "00-00000000000000000000000000000000-1111111111111111-01");
        var response = new MockHttpServletResponse();

        filter.doFilter(request, response, new MockFilterChain());

        assertThat(response.getHeader("traceparent")).matches(TRACEPARENT);
        assertThat(response.getHeader("X-Trace-Id")).hasSize(32).isNotEqualTo("00000000000000000000000000000000");
    }

    @Test
    void safelyNormalizesTheLegacyTraceHeader() throws Exception {
        var request = new MockHttpServletRequest("GET", "/health");
        request.addHeader("X-Trace-Id", "legacy-trace-identifier");
        var response = new MockHttpServletResponse();

        filter.doFilter(request, response, new MockFilterChain());

        assertThat(response.getHeader("X-Trace-Id"))
                .isEqualTo(TraceContext.normalizeTraceId("legacy-trace-identifier"));
    }
}
