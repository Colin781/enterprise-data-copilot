package com.example.copilot.integration;

import static com.github.tomakehurst.wiremock.client.WireMock.*;
import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.jwt;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.example.copilot.entity.AppUser;
import com.example.copilot.entity.Tenant;
import com.example.copilot.enums.UserRole;
import com.example.copilot.repository.AppUserRepository;
import com.example.copilot.repository.TenantRepository;
import com.example.copilot.support.PostgresRedisIntegrationTest;
import com.github.tomakehurst.wiremock.WireMockServer;
import com.github.tomakehurst.wiremock.core.WireMockConfiguration;
import java.time.Duration;
import java.util.List;
import java.util.Set;
import java.util.UUID;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.http.MediaType;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.request.RequestPostProcessor;

@SpringBootTest(properties = {"platform.execution.enabled=false", "platform.bootstrap.enabled=false"})
@AutoConfigureMockMvc
class IntelligenceApiIntegrationTest extends PostgresRedisIntegrationTest {
    static final WireMockServer AGENT = new WireMockServer(WireMockConfiguration.options().dynamicPort());
    static { AGENT.start(); }
    @DynamicPropertySource
    static void agent(DynamicPropertyRegistry registry) {
        registry.add("platform.agent.base-url", AGENT::baseUrl);
    }
    @AfterAll static void closeAgent() { AGENT.stop(); }
    @BeforeEach void resetAgent() { AGENT.resetAll(); }
    @Autowired MockMvc mvc;
    @Autowired TenantRepository tenants;
    @Autowired AppUserRepository users;
    @Autowired StringRedisTemplate redis;
    @Autowired JdbcTemplate jdbc;

    record Identity(UUID tenant, UUID user, RequestPostProcessor token) {}

    Identity identity(String role) {
        var tenant = tenants.save(new Tenant(UUID.randomUUID(), "graph-" + UUID.randomUUID(), "Graph tenant"));
        var user = users.save(new AppUser(UUID.randomUUID(), tenant.getId(), "user@graph.test", "unused",
                "Graph user", Set.of(UserRole.valueOf(role))));
        var token = jwt().jwt(j -> j.subject(user.getId().toString())
                .claim("tenant_id", tenant.getId().toString()).claim("roles", List.of(role)))
                .authorities(new SimpleGrantedAuthority("ROLE_" + role));
        return new Identity(tenant.getId(), user.getId(), token);
    }

    @Test void rejectsAnonymousAndNonAdminExtraction() throws Exception {
        mvc.perform(post("/api/graph/search").contentType(MediaType.APPLICATION_JSON).content("{}"))
                .andExpect(status().isUnauthorized());
        var user = identity("ANALYST");
        mvc.perform(post("/api/graph/extract").with(user.token())
                .contentType(MediaType.APPLICATION_JSON).content("{}"))
                .andExpect(status().isForbidden());
        AGENT.verify(0, postRequestedFor(urlEqualTo("/internal/v1/graph/extract")));
    }

    @Test void overwritesSpoofedIdentityAndAuditsRead() throws Exception {
        var user = identity("VIEWER");
        AGENT.stubFor(com.github.tomakehurst.wiremock.client.WireMock.post(urlEqualTo("/internal/v1/graph/search"))
                .willReturn(okJson("{\"nodes\":[],\"edges\":[],\"truncated\":false}")));
        mvc.perform(post("/api/graph/search").with(user.token())
                .header("X-Tenant-Id", UUID.randomUUID().toString()).header("X-User-Role", "ADMIN")
                .contentType(MediaType.APPLICATION_JSON).content("{}"))
                .andExpect(status().isOk());
        AGENT.verify(postRequestedFor(urlEqualTo("/internal/v1/graph/search"))
                .withHeader("X-Tenant-Id", equalTo(user.tenant().toString()))
                .withHeader("X-User-Role", equalTo("VIEWER")));
        assertThat(jdbc.queryForObject("SELECT count(*) FROM copilot.audit_events "
                + "WHERE tenant_id=? AND action='GRAPH_search' AND outcome='SUCCESS'",
                Integer.class, user.tenant())).isEqualTo(1);
    }

    @Test void rateLimitAndUpstreamErrorsAreBoundedAndAudited() throws Exception {
        var user = identity("ANALYST");
        redis.opsForValue().set("copilot:intelligence:rate:" + user.tenant() + ":" + user.user(), "60", Duration.ofSeconds(60));
        mvc.perform(post("/api/mcp").with(user.token()).contentType(MediaType.APPLICATION_JSON).content("{}"))
                .andExpect(status().isTooManyRequests());
        var second = identity("ADMIN");
        AGENT.stubFor(com.github.tomakehurst.wiremock.client.WireMock.post(urlEqualTo("/internal/mcp/")).willReturn(aResponse().withStatus(503)));
        mvc.perform(post("/api/mcp").with(second.token()).contentType(MediaType.APPLICATION_JSON).content("{}"))
                .andExpect(status().isServiceUnavailable());
        assertThat(jdbc.queryForObject("SELECT count(*) FROM copilot.audit_events "
                + "WHERE tenant_id=? AND outcome='FAILED'", Integer.class, second.tenant())).isEqualTo(1);
    }
}
