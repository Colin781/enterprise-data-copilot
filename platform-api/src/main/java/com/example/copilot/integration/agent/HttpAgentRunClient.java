package com.example.copilot.integration.agent;

import com.example.copilot.common.TraceContext;
import io.micrometer.core.instrument.Counter;
import io.micrometer.core.instrument.MeterRegistry;
import io.micrometer.core.instrument.Timer;
import java.net.http.HttpClient;
import java.time.Instant;
import java.util.Map;
import java.util.UUID;
import java.util.function.Supplier;
import org.springframework.http.client.JdkClientHttpRequestFactory;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;
import tools.jackson.databind.ObjectMapper;

@Component
public class HttpAgentRunClient implements AgentRunClient {

    private final RestClient client;
    private final String serviceToken;
    private final ObjectMapper objectMapper;
    private final MeterRegistry meterRegistry;

    public HttpAgentRunClient(
            AgentIntegrationProperties properties, ObjectMapper objectMapper, MeterRegistry meterRegistry) {
        var httpClient = HttpClient.newBuilder()
                .version(HttpClient.Version.HTTP_1_1)
                .connectTimeout(properties.connectTimeout())
                .build();
        var requestFactory = new JdkClientHttpRequestFactory(httpClient);
        requestFactory.setReadTimeout(properties.requestTimeout());

        client = RestClient.builder()
                .requestFactory(requestFactory)
                .baseUrl(properties.baseUrl().toString())
                .build();
        serviceToken = properties.serviceToken();
        this.objectMapper = objectMapper;
        this.meterRegistry = meterRegistry;
    }

    @Override
    public AgentRunResult start(
            UUID jobId,
            UUID tenantId,
            UUID userId,
            String role,
            UUID dataSourceId,
            String question,
            String traceId,
            String idempotencyKey) {
        return observe("start", () -> {
            var response = client.post()
                    .uri("/internal/v1/runs")
                    .header("Authorization", "Bearer " + serviceToken)
                    .header("X-Tenant-Id", tenantId.toString())
                    .header("X-User-Id", userId.toString())
                    .header("X-User-Role", role)
                    .header("Idempotency-Key", idempotencyKey)
                    .header("traceparent", TraceContext.childTraceparent(traceId))
                    .body(Map.of(
                            "job_id", jobId.toString(),
                            "data_source_id", dataSourceId.toString(),
                            "question", question,
                            "requested_at", Instant.now().toString()))
                    .retrieve()
                    .body(String.class);
            var body = responseBody(response);
            return new AgentRunResult(requiredText(body, "run_id"), requiredText(body, "status"), requiredState(body));
        });
    }

    @Override
    public AgentResumeResult resume(
            UUID jobId,
            UUID tenantId,
            UUID approvalId,
            UUID decidedBy,
            String decision,
            String comment,
            String traceId) {
        return observe("resume", () -> {
            var response = client.post()
                    .uri("/internal/v1/runs/{runId}/resume", jobId)
                    .header("Authorization", "Bearer " + serviceToken)
                    .header("X-Tenant-Id", tenantId.toString())
                    .header("X-User-Role", "ADMIN")
                    .header("traceparent", TraceContext.childTraceparent(traceId))
                    .body(Map.of(
                            "approval_id",
                            approvalId.toString(),
                            "decision",
                            decision,
                            "decided_by",
                            decidedBy.toString(),
                            "comment",
                            comment == null ? "" : comment))
                    .retrieve()
                    .body(String.class);
            var body = responseBody(response);
            return new AgentResumeResult(
                    requiredText(body, "run_id"), requiredText(body, "status"), requiredState(body));
        });
    }

    private tools.jackson.databind.JsonNode responseBody(String response) {
        if (response == null || response.isBlank()) {
            throw new AgentProtocolException();
        }
        try {
            var body = objectMapper.readTree(response);
            if (body == null || !body.isObject()) {
                throw new AgentProtocolException();
            }
            return body;
        } catch (AgentProtocolException exception) {
            throw exception;
        } catch (RuntimeException exception) {
            throw new AgentProtocolException(exception);
        }
    }

    private static String requiredText(tools.jackson.databind.JsonNode body, String field) {
        var value = body.get(field);
        if (value == null || !value.isTextual() || value.asText().isBlank()) {
            throw new AgentProtocolException();
        }
        return value.asText();
    }

    private static tools.jackson.databind.JsonNode requiredState(tools.jackson.databind.JsonNode body) {
        var state = body.get("state");
        if (state == null || !state.isObject()) {
            throw new AgentProtocolException();
        }
        return state;
    }

    private <T> T observe(String operation, Supplier<T> call) {
        var sample = Timer.start(meterRegistry);
        try {
            return call.get();
        } catch (RuntimeException exception) {
            Counter.builder("copilot.agent.client.errors")
                    .description("Agent Service client failures.")
                    .tag("operation", operation)
                    .register(meterRegistry)
                    .increment();
            throw exception;
        } finally {
            sample.stop(Timer.builder("copilot.agent.client.duration")
                    .description("Agent Service client latency.")
                    .tag("operation", operation)
                    .publishPercentileHistogram()
                    .register(meterRegistry));
        }
    }
}
