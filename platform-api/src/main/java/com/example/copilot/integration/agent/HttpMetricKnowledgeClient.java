package com.example.copilot.integration.agent;

import com.example.copilot.knowledge.api.MetricDocumentResource;
import com.example.copilot.knowledge.api.MetricDocumentUploadRequest;
import java.net.http.HttpClient;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HexFormat;
import java.util.Map;
import java.util.UUID;
import org.springframework.http.client.JdkClientHttpRequestFactory;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;
import tools.jackson.databind.ObjectMapper;

@Component
public class HttpMetricKnowledgeClient implements MetricKnowledgeClient {

    private final RestClient client;
    private final String serviceToken;
    private final ObjectMapper objectMapper;

    public HttpMetricKnowledgeClient(AgentIntegrationProperties properties, ObjectMapper objectMapper) {
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
    public MetricDocumentResource ingest(
            UUID tenantId, UUID userId, MetricDocumentUploadRequest request, String traceId) {
        var response = client.post()
                .uri("/internal/v1/knowledge/documents")
                .header("Authorization", "Bearer " + serviceToken)
                .header("X-Tenant-Id", tenantId.toString())
                .header("X-User-Id", userId.toString())
                .header("traceparent", traceparent(traceId))
                .body(Map.of(
                        "title", request.title().trim(),
                        "source_name", request.sourceName(),
                        "source_type", request.sourceType(),
                        "content_base64", request.contentBase64()))
                .retrieve()
                .body(String.class);

        return objectMapper.readValue(response, MetricDocumentResource.class);
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
