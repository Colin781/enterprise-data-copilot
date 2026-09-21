package com.example.copilot.platform;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.example.copilot.PostgresIntegrationTest;
import com.example.copilot.analysis.domain.AnalysisJob;
import com.example.copilot.analysis.repository.AnalysisJobRepository;
import com.example.copilot.approval.repository.ApprovalRepository;
import com.example.copilot.audit.repository.AuditEventRepository;
import com.example.copilot.datasource.domain.DataSource;
import com.example.copilot.datasource.repository.DataSourceRepository;
import com.example.copilot.identity.domain.AppUser;
import com.example.copilot.identity.domain.Tenant;
import com.example.copilot.identity.domain.UserRole;
import com.example.copilot.identity.repository.AppUserRepository;
import com.example.copilot.identity.repository.TenantRepository;
import com.example.copilot.integration.agent.MetricKnowledgeClient;
import com.example.copilot.knowledge.api.MetricDocumentResource;
import jakarta.persistence.EntityManagerFactory;
import jakarta.persistence.OptimisticLockException;
import java.time.Instant;
import java.util.Set;
import java.util.UUID;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.http.MediaType;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;
import tools.jackson.databind.ObjectMapper;

@SpringBootTest
@AutoConfigureMockMvc
class PlatformSecurityIntegrationTest extends PostgresIntegrationTest {

    private static final String PASSWORD = "correct-horse-battery-staple";
    private static final String IDEMPOTENCY_KEY = "1234567890abcdef";

    @Autowired
    MockMvc mockMvc;

    @Autowired
    ObjectMapper objectMapper;

    @Autowired
    PasswordEncoder passwordEncoder;

    @Autowired
    TenantRepository tenantRepository;

    @Autowired
    AppUserRepository userRepository;

    @Autowired
    DataSourceRepository dataSourceRepository;

    @Autowired
    AnalysisJobRepository jobRepository;

    @Autowired
    ApprovalRepository approvalRepository;

    @Autowired
    AuditEventRepository auditEventRepository;

    @Autowired
    EntityManagerFactory entityManagerFactory;

    @Autowired
    JdbcTemplate jdbcTemplate;

    @MockitoBean
    MetricKnowledgeClient metricKnowledgeClient;

    @BeforeEach
    void cleanDatabase() {
        approvalRepository.deleteAllInBatch();
        auditEventRepository.deleteAllInBatch();
        jobRepository.deleteAllInBatch();
        dataSourceRepository.deleteAllInBatch();
        userRepository.deleteAllInBatch();
        tenantRepository.deleteAllInBatch();
    }

    @Test
    void authenticationIsRequiredAndInvalidCredentialsHaveStableSafeErrors() throws Exception {
        mockMvc.perform(post("/api/analysis/jobs")
                        .header("Idempotency-Key", IDEMPOTENCY_KEY)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(jobRequest(UUID.randomUUID(), "sales by month")))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.code").value("AUTHENTICATION_REQUIRED"))
                .andExpect(jsonPath("$.trace_id").isNotEmpty())
                .andExpect(header().exists("X-Trace-Id"));

        createUser("alpha", "analyst@alpha.test", UserRole.ANALYST);
        mockMvc.perform(post("/api/auth/login")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(loginRequest("alpha", "analyst@alpha.test", "wrong-password")))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.code").value("AUTHENTICATION_FAILED"))
                .andExpect(jsonPath("$.message").value("Invalid credentials."));
    }

    @Test
    void internalServiceTokenBypassesJwtParsingAndIsStillValidated() throws Exception {
        var jobId = UUID.randomUUID();
        var body =
                """
                {
                  "step_name": "classify",
                  "status": "SUCCEEDED",
                  "attempt": 0,
                  "input_summary": {},
                  "output_summary": {},
                  "duration_ms": 1,
                  "error_code": null
                }
                """;

        mockMvc.perform(post("/internal/v1/analysis/jobs/{jobId}/steps", jobId)
                        .header("Authorization", "Bearer wrong-service-token")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(body))
                .andExpect(status().isForbidden());

        mockMvc.perform(post("/internal/v1/analysis/jobs/{jobId}/steps", jobId)
                        .header("Authorization", "Bearer test-only-agent-service-token")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(body))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.code").value("RESOURCE_NOT_FOUND"));
    }

    @Test
    void rolesRestrictAdministrativeAndAnalysisOperations() throws Exception {
        var analyst = createUser("alpha", "analyst@alpha.test", UserRole.ANALYST);
        var viewer = createUser(analyst.tenant(), "viewer@alpha.test", UserRole.VIEWER);
        var analystToken = login("alpha", "analyst@alpha.test");
        var viewerToken = login("alpha", "viewer@alpha.test");

        mockMvc.perform(post("/api/data-sources")
                        .header("Authorization", bearer(analystToken))
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(dataSourceRequest("alpha-source")))
                .andExpect(status().isForbidden())
                .andExpect(jsonPath("$.code").value("ACCESS_DENIED"));

        mockMvc.perform(post("/api/approvals/{id}/approve", UUID.randomUUID())
                        .header("Authorization", bearer(analystToken))
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{}"))
                .andExpect(status().isForbidden())
                .andExpect(jsonPath("$.code").value("ACCESS_DENIED"));

        mockMvc.perform(post("/api/analysis/jobs")
                        .header("Authorization", bearer(viewerToken))
                        .header("Idempotency-Key", IDEMPOTENCY_KEY)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(jobRequest(UUID.randomUUID(), "sales by month")))
                .andExpect(status().isForbidden())
                .andExpect(jsonPath("$.code").value("ACCESS_DENIED"));
    }

    @Test
    void administratorRegistersOnlyTenantScopedMetadataWithoutReturningSecrets() throws Exception {
        createUser("alpha", "admin@alpha.test", UserRole.ADMIN);
        var token = login("alpha", "admin@alpha.test");

        mockMvc.perform(post("/api/data-sources")
                        .header("Authorization", bearer(token))
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(dataSourceRequest("northwind")))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.name").value("northwind"))
                .andExpect(jsonPath("$.source_type").value("POSTGRESQL"))
                .andExpect(jsonPath("$.allowed_schema").value("northwind"))
                .andExpect(jsonPath("$.host").doesNotExist())
                .andExpect(jsonPath("$.secret_ref").doesNotExist());

        assertThat(auditEventRepository.countByTenantIdAndAction(
                        tenantRepository
                                .findBySlugAndEnabledTrue("alpha")
                                .orElseThrow()
                                .getId(),
                        "DATA_SOURCE_CREATED"))
                .isEqualTo(1);
    }

    @Test
    void deploymentAllowlistRejectsArbitraryPublicDatabaseHosts() throws Exception {
        createUser("alpha", "admin@alpha.test", UserRole.ADMIN);
        var token = login("alpha", "admin@alpha.test");
        var body =
                """
                {
                  "name": "untrusted",
                  "host": "public-database.example.com",
                  "port": 5432,
                  "database_name": "production",
                  "allowed_schema": "public",
                  "secret_ref": "vault:production/database"
                }
                """;

        mockMvc.perform(post("/api/data-sources")
                        .header("Authorization", bearer(token))
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(body))
                .andExpect(status().isUnprocessableContent())
                .andExpect(jsonPath("$.code").value("DATA_SOURCE_HOST_NOT_ALLOWED"))
                .andExpect(jsonPath("$.message").value("The data source host is not available in this deployment."));

        assertThat(dataSourceRepository.count()).isZero();
    }

    @Test
    void onlyAdministratorCanUploadMetricKnowledgeThroughThePlatformBoundary() throws Exception {
        var admin = createUser("alpha", "admin@alpha.test", UserRole.ADMIN);
        createUser(admin.tenant(), "analyst@alpha.test", UserRole.ANALYST);
        var documentId = UUID.randomUUID();
        var now = Instant.now();
        when(metricKnowledgeClient.ingest(any(), any(), any(), any()))
                .thenReturn(new MetricDocumentResource(
                        documentId,
                        admin.tenant().getId(),
                        "Revenue",
                        1,
                        "ACTIVE",
                        "MARKDOWN",
                        "metrics.md",
                        "0".repeat(64),
                        1,
                        now,
                        now));
        var body =
                """
                {"title":"Revenue","source_name":"metrics.md","source_type":"MARKDOWN","content_base64":"IyBSZXZlbnVl"}
                """;

        mockMvc.perform(post("/api/metric-documents")
                        .header("Authorization", bearer(login("alpha", "analyst@alpha.test")))
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(body))
                .andExpect(status().isForbidden());

        mockMvc.perform(post("/api/metric-documents")
                        .header("Authorization", bearer(login("alpha", "admin@alpha.test")))
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(body))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.id").value(documentId.toString()))
                .andExpect(jsonPath("$.chunk_count").value(1));

        assertThat(auditEventRepository.countByTenantIdAndAction(admin.tenant().getId(), "METRIC_DOCUMENT_UPLOADED"))
                .isEqualTo(1);
    }

    @Test
    void repeatedCreateWithSameKeyReturnsSameJobAndDifferentPayloadConflicts() throws Exception {
        var analyst = createUser("alpha", "analyst@alpha.test", UserRole.ANALYST);
        var source = dataSourceRepository.save(dataSource(analyst.tenant().getId(), "northwind"));
        var token = login("alpha", "analyst@alpha.test");

        var first = mockMvc.perform(post("/api/analysis/jobs")
                        .header("Authorization", bearer(token))
                        .header("Idempotency-Key", IDEMPOTENCY_KEY)
                        .header("X-Trace-Id", "0123456789abcdef0123456789abcdef")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(jobRequest(source.getId(), "sales by month")))
                .andExpect(status().isAccepted())
                .andExpect(jsonPath("$.status").value("CREATED"))
                .andExpect(jsonPath("$.trace_id").value("0123456789abcdef0123456789abcdef"))
                .andReturn();
        var firstId = objectMapper
                .readTree(first.getResponse().getContentAsString())
                .get("id")
                .asString();

        mockMvc.perform(post("/api/analysis/jobs")
                        .header("Authorization", bearer(token))
                        .header("Idempotency-Key", IDEMPOTENCY_KEY)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(jobRequest(source.getId(), "sales by month")))
                .andExpect(status().isAccepted())
                .andExpect(jsonPath("$.id").value(firstId));

        mockMvc.perform(post("/api/analysis/jobs")
                        .header("Authorization", bearer(token))
                        .header("Idempotency-Key", IDEMPOTENCY_KEY)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(jobRequest(source.getId(), "a different question")))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.code").value("IDEMPOTENCY_CONFLICT"));

        assertThat(jobRepository.count()).isEqualTo(1);
        assertThat(auditEventRepository.countByTenantIdAndAction(
                        analyst.tenant().getId(), "ANALYSIS_JOB_CREATED"))
                .isEqualTo(1);
    }

    @Test
    void tenantAndOwnerBoundariesHideOtherTenantResources() throws Exception {
        var alpha = createUser("alpha", "analyst@alpha.test", UserRole.ANALYST);
        var beta = createUser("beta", "analyst@beta.test", UserRole.ANALYST);
        var betaSource = dataSourceRepository.save(dataSource(beta.tenant().getId(), "beta-source"));
        var betaJob = jobRepository.save(new AnalysisJob(
                UUID.randomUUID(),
                beta.tenant().getId(),
                betaSource.getId(),
                beta.user().getId(),
                "beta question",
                "beta-idempotency-key",
                "0".repeat(64),
                "1".repeat(32)));
        var alphaToken = login("alpha", "analyst@alpha.test");

        mockMvc.perform(post("/api/analysis/jobs")
                        .header("Authorization", bearer(alphaToken))
                        .header("Idempotency-Key", IDEMPOTENCY_KEY)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(jobRequest(betaSource.getId(), "try another tenant")))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.code").value("RESOURCE_NOT_FOUND"));

        mockMvc.perform(get("/api/analysis/jobs/{id}", betaJob.getId()).header("Authorization", bearer(alphaToken)))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.code").value("RESOURCE_NOT_FOUND"));

        mockMvc.perform(get("/api/analysis/jobs/{id}/events", betaJob.getId())
                        .header("Authorization", bearer(alphaToken)))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.code").value("RESOURCE_NOT_FOUND"));

        mockMvc.perform(get("/api/data-sources").header("Authorization", bearer(alphaToken)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$").isEmpty());

        mockMvc.perform(post("/api/analysis/jobs")
                        .header("Authorization", bearer(alphaToken))
                        .header("Idempotency-Key", "fedcba0987654321")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(
                                """
                                {
                                  "data_source_id": "%s",
                                  "question": "normal question",
                                  "tenant_id": "%s"
                                }
                                """
                                        .formatted(
                                                betaSource.getId(),
                                                beta.tenant().getId())))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.code").value("MALFORMED_REQUEST"));

        assertThat(jobRepository.count()).isEqualTo(1);
        assertThat(alpha.user().getTenantId()).isEqualTo(alpha.tenant().getId());
    }

    @Test
    void optimisticLockRejectsAStaleDataSourceUpdate() {
        var admin = createUser("alpha", "admin@alpha.test", UserRole.ADMIN);
        var source = dataSourceRepository.save(dataSource(admin.tenant().getId(), "original"));
        var firstManager = entityManagerFactory.createEntityManager();
        var secondManager = entityManagerFactory.createEntityManager();
        var firstTransaction = firstManager.getTransaction();
        var secondTransaction = secondManager.getTransaction();

        try {
            firstTransaction.begin();
            secondTransaction.begin();
            var firstCopy = firstManager.find(DataSource.class, source.getId());
            var staleCopy = secondManager.find(DataSource.class, source.getId());
            firstCopy.rename("first update");
            staleCopy.rename("stale update");
            firstTransaction.commit();

            assertThatThrownBy(secondTransaction::commit).hasCauseInstanceOf(OptimisticLockException.class);
        } finally {
            if (firstTransaction.isActive()) {
                firstTransaction.rollback();
            }
            if (secondTransaction.isActive()) {
                secondTransaction.rollback();
            }
            firstManager.close();
            secondManager.close();
        }
    }

    @Test
    void metricKnowledgeMigrationCreatesVectorBackedTenantTables() {
        assertThat(jdbcTemplate.queryForObject(
                        "SELECT extname FROM pg_extension WHERE extname = 'vector'", String.class))
                .isEqualTo("vector");
        assertThat(jdbcTemplate.queryForObject("SELECT to_regclass('copilot.metric_documents')::text", String.class))
                .isEqualTo("copilot.metric_documents");
        assertThat(jdbcTemplate.queryForObject(
                        "SELECT format_type(atttypid, atttypmod) "
                                + "FROM pg_attribute "
                                + "WHERE attrelid = 'copilot.metric_chunks'::regclass "
                                + "AND attname = 'embedding'",
                        String.class))
                .isEqualTo("vector(64)");
        assertThat(jdbcTemplate.queryForObject("SELECT to_regclass('copilot.agent_steps')::text", String.class))
                .isEqualTo("copilot.agent_steps");
    }

    private Fixture createUser(String tenantSlug, String email, UserRole role) {
        var tenant = tenantRepository.save(new Tenant(UUID.randomUUID(), tenantSlug, tenantSlug.toUpperCase()));
        return createUser(tenant, email, role);
    }

    private Fixture createUser(Tenant tenant, String email, UserRole role) {
        var user = userRepository.save(new AppUser(
                UUID.randomUUID(), tenant.getId(), email, passwordEncoder.encode(PASSWORD), email, Set.of(role)));
        return new Fixture(tenant, user);
    }

    private DataSource dataSource(UUID tenantId, String name) {
        return new DataSource(
                UUID.randomUUID(),
                tenantId,
                name,
                "business-db",
                5432,
                "northwind",
                "northwind",
                "env:BUSINESS_DB_READONLY_PASSWORD");
    }

    private String login(String tenantSlug, String email) throws Exception {
        var result = mockMvc.perform(post("/api/auth/login")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(loginRequest(tenantSlug, email, PASSWORD)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.token_type").value("Bearer"))
                .andExpect(jsonPath("$.access_token").isNotEmpty())
                .andReturn();
        return objectMapper
                .readTree(result.getResponse().getContentAsString())
                .get("access_token")
                .asString();
    }

    private String loginRequest(String tenantSlug, String email, String password) {
        return """
                {"tenant_slug":"%s","email":"%s","password":"%s"}
                """
                .formatted(tenantSlug, email, password);
    }

    private String dataSourceRequest(String name) {
        return """
                {
                  "name": "%s",
                  "host": "business-db",
                  "port": 5432,
                  "database_name": "northwind",
                  "allowed_schema": "northwind",
                  "secret_ref": "env:BUSINESS_DB_READONLY_PASSWORD"
                }
                """
                .formatted(name);
    }

    private String jobRequest(UUID sourceId, String question) {
        return """
                {"data_source_id":"%s","question":"%s"}
                """
                .formatted(sourceId, question);
    }

    private String bearer(String token) {
        return "Bearer " + token;
    }

    private record Fixture(Tenant tenant, AppUser user) {}
}
