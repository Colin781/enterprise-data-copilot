package com.example.copilot.integration.agent;

import java.net.http.HttpClient;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.Instant;
import java.util.HexFormat;
import java.util.Map;
import java.util.UUID;
import org.springframework.http.client.JdkClientHttpRequestFactory;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;
import tools.jackson.databind.ObjectMapper;

@Component
public class HttpAgentRunClient implements AgentRunClient {

    private final RestClient client;
    private final String serviceToken;
    private final ObjectMapper objectMapper;

    public HttpAgentRunClient(AgentIntegrationProperties properties, ObjectMapper objectMapper) {
        var httpClient =
                HttpClient.newBuilder().version(HttpClient.Version.HTTP_1_1).build();

        client = RestClient.builder()
                .requestFactory(new JdkClientHttpRequestFactory(httpClient))
                .baseUrl(properties.baseUrl().toString())
                .build();
        serviceToken = properties.serviceToken();
        this.objectMapper = objectMapper;
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
        var response = client.post()
                .uri("/internal/v1/runs")
                .header("Authorization", "Bearer " + serviceToken)
                .header("X-Tenant-Id", tenantId.toString())
                .header("X-User-Id", userId.toString())
                .header("X-User-Role", role)
                .header("Idempotency-Key", idempotencyKey)
                .header("traceparent", traceparent(traceId))
                .body(Map.of(
                        "job_id", jobId.toString(),
                        "data_source_id", dataSourceId.toString(),
                        "question", question,
                        "requested_at", Instant.now().toString()))
                .retrieve()
                .body(String.class);
        var body = objectMapper.readTree(response);
        return new AgentRunResult(
                body.get("run_id").asText(), body.get("status").asText(), body.get("state"));
    }

    @Override
    public AgentResumeResult resume(
            UUID jobId, UUID tenantId, UUID approvalId, UUID decidedBy, String decision, String comment) {
        var response = client.post()
                .uri("/internal/v1/runs/{runId}/resume", jobId)
                .header("Authorization", "Bearer " + serviceToken)
                .header("X-Tenant-Id", tenantId.toString())
                .header("X-User-Role", "ADMIN")
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
        var body = objectMapper.readTree(response);
        return new AgentResumeResult(
                body.get("run_id").asText(), body.get("status").asText(), body.get("state"));
    }

    private static String traceparent(String traceId) {
        var normalized = traceId.matches("[0-9a-fA-F]{32}")
                ? traceId.toLowerCase()
                : sha256(traceId).substring(0, 32);
        return "00-" + normalized + "-0000000000000001-01";
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
