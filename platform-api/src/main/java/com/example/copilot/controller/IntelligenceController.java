package com.example.copilot.controller;

import com.example.copilot.common.TraceContext;
import com.example.copilot.config.properties.AgentIntegrationProperties;
import com.example.copilot.security.CallerIdentity;
import com.example.copilot.service.AuditService;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.constraints.Size;
import java.net.http.HttpClient;
import java.util.Set;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.http.client.JdkClientHttpRequestFactory;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.security.oauth2.server.resource.authentication.JwtAuthenticationToken;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.client.RestClient;

/** Public JWT boundary for graph/RAG/MCP. Identity headers never come from the caller. */
@RestController
@Validated
@PreAuthorize("hasAnyRole('ADMIN','ANALYST','VIEWER')")
public class IntelligenceController {
    private final RestClient client;
    private final AgentIntegrationProperties properties;
    private final CallerIdentity identities;
    private final AuditService audit;
    private final StringRedisTemplate redis;

    public IntelligenceController(AgentIntegrationProperties properties, CallerIdentity identities,
                                  AuditService audit, StringRedisTemplate redis) {
        this.properties = properties;
        this.identities = identities;
        this.audit = audit;
        this.redis = redis;
        var http = HttpClient.newBuilder().connectTimeout(properties.connectTimeout())
                .version(HttpClient.Version.HTTP_1_1).build();
        var factory = new JdkClientHttpRequestFactory(http);
        factory.setReadTimeout(properties.requestTimeout());
        this.client = RestClient.builder().baseUrl(properties.baseUrl().toString())
                .requestFactory(factory).build();
    }

    @PostMapping("/api/graph/{operation}")
    public ResponseEntity<String> graph(@PathVariable String operation,
            @RequestBody @Size(max = 150000) String body, JwtAuthenticationToken authentication,
            HttpServletRequest request) {
        if (!Set.of("extract", "search", "path", "answer").contains(operation)) {
            return ResponseEntity.status(HttpStatus.NOT_FOUND).body("{\"code\":\"NOT_FOUND\"}");
        }
        var caller = identities.current(authentication);
        if (operation.equals("extract") && !caller.roles().contains("ADMIN")) {
            throw new AccessDeniedException("Administrator role required");
        }
        return forward("/internal/v1/graph/" + operation, body, authentication, request, "GRAPH_" + operation);
    }

    @PostMapping("/api/knowledge/search")
    public ResponseEntity<String> search(@RequestBody @Size(max = 20000) String body,
            JwtAuthenticationToken authentication, HttpServletRequest request) {
        return forward("/internal/v1/knowledge/search", body, authentication, request, "KNOWLEDGE_SEARCH");
    }

    @PostMapping("/api/mcp")
    public ResponseEntity<String> mcp(@RequestBody @Size(max = 32768) String body,
            JwtAuthenticationToken authentication, HttpServletRequest request) {
        return forward("/internal/mcp/", body, authentication, request, "MCP_REQUEST");
    }

    private ResponseEntity<String> forward(String path, String body,
            JwtAuthenticationToken authentication, HttpServletRequest request, String action) {
        var caller = identities.current(authentication);
        var traceId = TraceContext.current(request);
        // Shared across platform replicas; keys expire even if a process dies after INCR.
        var key = "copilot:intelligence:rate:" + caller.tenantId() + ":" + caller.userId();
        var script = new org.springframework.data.redis.core.script.DefaultRedisScript<Long>(
                "local n=redis.call('INCR',KEYS[1]); if n==1 then redis.call('EXPIRE',KEYS[1],60) end; return n",
                Long.class);
        var count = redis.execute(script, java.util.List.of(key));
        if (count != null && count > 60) {
            audit.recordOutcome(caller.tenantId(), caller.userId(), action, "RATE_LIMITED", traceId);
            return ResponseEntity.status(429).header("Retry-After", "60")
                    .body("{\"code\":\"RATE_LIMITED\",\"message\":\"Please retry later.\"}");
        }
        try {
            var role = caller.roles().contains("ADMIN") ? "ADMIN"
                    : caller.roles().contains("ANALYST") ? "ANALYST" : "VIEWER";
            return client.post().uri(path).contentType(MediaType.APPLICATION_JSON)
                    .header("Accept", "application/json, text/event-stream")
                    .header("Authorization", "Bearer " + properties.serviceToken())
                    .header("X-Tenant-Id", caller.tenantId().toString())
                    .header("X-User-Id", caller.userId().toString())
                    .header("X-User-Role", role)
                    .header("X-Caller-Token", authentication.getToken().getTokenValue())
                    .header("traceparent", TraceContext.childTraceparent(traceId))
                    .body(body).exchange((req, response) -> {
                        var bytes = response.getBody().readNBytes(2000001);
                        if (bytes.length > 2000000) throw new IllegalStateException("Upstream response too large");
                        audit.recordOutcome(caller.tenantId(), caller.userId(), action,
                                response.getStatusCode().is2xxSuccessful() ? "SUCCESS" : "FAILED", traceId);
                        return ResponseEntity.status(response.getStatusCode()).contentType(MediaType.APPLICATION_JSON)
                                .body(new String(bytes, java.nio.charset.StandardCharsets.UTF_8));
                    });
        } catch (Exception error) {
            audit.recordOutcome(caller.tenantId(), caller.userId(), action, "FAILED", traceId);
            return ResponseEntity.status(502).contentType(MediaType.APPLICATION_JSON)
                    .body("{\"code\":\"INTELLIGENCE_UNAVAILABLE\",\"message\":\"AI service unavailable.\"}");
        }
    }
}
