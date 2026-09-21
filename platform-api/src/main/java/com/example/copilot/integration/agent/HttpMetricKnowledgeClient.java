package com.example.copilot.integration.agent;

import com.example.copilot.common.TraceContext;
import com.example.copilot.knowledge.api.MetricDocumentResource;
import com.example.copilot.knowledge.api.MetricDocumentUploadRequest;
import java.net.http.HttpClient;
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
                .header("traceparent", TraceContext.childTraceparent(traceId))
                .body(Map.of(
                        "title", request.title().trim(),
                        "source_name", request.sourceName(),
                        "source_type", request.sourceType(),
                        "content_base64", request.contentBase64()))
                .retrieve()
                .body(String.class);

        return objectMapper.readValue(response, MetricDocumentResource.class);
    }
}
