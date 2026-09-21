package com.example.copilot.integration.agent;

import static com.github.tomakehurst.wiremock.client.WireMock.aResponse;
import static com.github.tomakehurst.wiremock.client.WireMock.post;
import static com.github.tomakehurst.wiremock.client.WireMock.urlEqualTo;
import static com.github.tomakehurst.wiremock.core.WireMockConfiguration.wireMockConfig;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import com.github.tomakehurst.wiremock.WireMockServer;
import io.micrometer.core.instrument.simple.SimpleMeterRegistry;
import java.net.URI;
import java.time.Duration;
import java.util.UUID;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.web.client.HttpServerErrorException;
import org.springframework.web.client.ResourceAccessException;
import tools.jackson.databind.ObjectMapper;

class HttpAgentRunClientFailureTest {

    private WireMockServer wireMock;

    @BeforeEach
    void startServer() {
        wireMock = new WireMockServer(wireMockConfig().dynamicPort());
        wireMock.start();
    }

    @AfterEach
    void stopServer() {
        if (wireMock != null) {
            wireMock.stop();
        }
    }

    @Test
    void mapsAgent500ToHttpServerErrorWithoutLeakingBody() {
        wireMock.stubFor(post(urlEqualTo("/internal/v1/runs"))
                .willReturn(aResponse().withStatus(500).withBody("internal database details")));

        var error = assertThrows(HttpServerErrorException.class, () -> start(client(Duration.ofSeconds(1))));

        assertEquals(500, error.getStatusCode().value());
    }

    @Test
    void rejectsMalformedAgentJsonAsAStableProtocolFailure() {
        wireMock.stubFor(post(urlEqualTo("/internal/v1/runs"))
                .willReturn(aResponse().withStatus(202).withBody("{")));

        var error = assertThrows(AgentProtocolException.class, () -> start(client(Duration.ofSeconds(1))));

        assertEquals("Agent Service returned an invalid response.", error.getMessage());
    }

    @Test
    void rejectsStructurallyIncompleteAgentResponse() {
        wireMock.stubFor(post(urlEqualTo("/internal/v1/runs"))
                .willReturn(aResponse().withStatus(202).withBody("{\"run_id\":\"run-1\"}")));

        assertThrows(AgentProtocolException.class, () -> start(client(Duration.ofSeconds(1))));
    }

    @Test
    void enforcesAgentRequestTimeout() {
        wireMock.stubFor(post(urlEqualTo("/internal/v1/runs"))
                .willReturn(aResponse().withStatus(202).withFixedDelay(250).withBody(validResponse())));

        assertThrows(ResourceAccessException.class, () -> start(client(Duration.ofMillis(50))));
    }

    @Test
    void acceptsACompleteAgentResponse() {
        wireMock.stubFor(post(urlEqualTo("/internal/v1/runs"))
                .willReturn(aResponse().withStatus(202).withBody(validResponse())));

        var result = start(client(Duration.ofSeconds(1)));

        assertEquals("run-1", result.runId());
        assertEquals("COMPLETED", result.status());
        assertEquals("answer", result.state().get("answer").asText());
    }

    private HttpAgentRunClient client(Duration requestTimeout) {
        var properties = new AgentIntegrationProperties(
                "test-service-token", URI.create(wireMock.baseUrl()), Duration.ofSeconds(1), requestTimeout);
        return new HttpAgentRunClient(properties, new ObjectMapper(), new SimpleMeterRegistry());
    }

    private static AgentRunResult start(HttpAgentRunClient client) {
        return client.start(
                UUID.randomUUID(),
                UUID.randomUUID(),
                UUID.randomUUID(),
                "ANALYST",
                UUID.randomUUID(),
                "sales by month",
                "1234567890abcdef1234567890abcdef",
                "p10-idempotency-key");
    }

    private static String validResponse() {
        return "{\"run_id\":\"run-1\",\"status\":\"COMPLETED\",\"state\":{\"answer\":\"answer\"}}";
    }
}
