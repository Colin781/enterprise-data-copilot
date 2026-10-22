package com.example.copilot.integration;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.example.copilot.config.properties.SecurityProperties;
import com.example.copilot.entity.AppUser;
import com.example.copilot.entity.DataSource;
import com.example.copilot.entity.Tenant;
import com.example.copilot.enums.AnalysisJobStatus;
import com.example.copilot.enums.UserRole;
import com.example.copilot.repository.AppUserRepository;
import com.example.copilot.repository.DataSourceRepository;
import com.example.copilot.repository.TenantRepository;
import com.example.copilot.support.PostgresIntegrationTest;
import java.sql.Timestamp;
import java.time.Instant;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.oauth2.jose.jws.MacAlgorithm;
import org.springframework.security.oauth2.jwt.JwsHeader;
import org.springframework.security.oauth2.jwt.JwtClaimsSet;
import org.springframework.security.oauth2.jwt.JwtEncoder;
import org.springframework.security.oauth2.jwt.JwtEncoderParameters;
import org.springframework.test.web.servlet.MockMvc;

@SpringBootTest(properties = {
        "platform.execution.enabled=false",
        "platform.bootstrap.enabled=false"
})
@AutoConfigureMockMvc
class AnalysisJobSearchApiIntegrationTest extends PostgresIntegrationTest {

    private static final String PATH = "/api/analysis/jobs/search";

    private static final Instant START =
            Instant.parse("2026-10-01T00:00:00Z");

    private static final Instant END = START.plusSeconds(3600);

    @Autowired
    MockMvc mockMvc;

    @Autowired
    TenantRepository tenants;

    @Autowired
    AppUserRepository users;

    @Autowired
    DataSourceRepository dataSources;

    @Autowired
    JdbcTemplate jdbcTemplate;

    @Autowired
    JwtEncoder jwtEncoder;

    @Autowired
    SecurityProperties securityProperties;

    @Test
    void authenticationIsRequired() throws Exception {
        mockMvc.perform(get(PATH))
                .andExpect(status().isUnauthorized());
    }

    @Test
    void unsupportedRoleIsForbidden() throws Exception {
        var user = createContext(createTenant(), UserRole.VIEWER);

        mockMvc.perform(get(PATH)
                        .header(
                                "Authorization",
                                "Bearer " + token(user, List.of("UNSUPPORTED"))))
                .andExpect(status().isForbidden());
    }

    @Test
    void adminSeesOnlyCurrentTenantJobsAndJoinedNames() throws Exception {
        var alpha = createTenant();
        var admin = createContext(alpha, UserRole.ADMIN);
        var analyst = createContext(alpha, UserRole.ANALYST);
        var beta = createContext(createTenant(), UserRole.ADMIN);

        var visibleId = insertJob(
                analyst,
                AnalysisJobStatus.RUNNING,
                "销售分析",
                START);

        insertJob(
                beta,
                AnalysisJobStatus.RUNNING,
                "其他租户任务",
                START);

        mockMvc.perform(get(PATH)
                        .header("Authorization", bearer(admin)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.total").value(1))
                .andExpect(jsonPath("$.page").value(1))
                .andExpect(jsonPath("$.size").value(20))
                .andExpect(jsonPath("$.total_pages").value(1))
                .andExpect(jsonPath("$.items.length()").value(1))
                .andExpect(jsonPath("$.items[0].id")
                        .value(visibleId.toString()))
                .andExpect(jsonPath("$.items[0].data_source_id")
                        .value(analyst.sourceId().toString()))
                .andExpect(jsonPath("$.items[0].data_source_name")
                        .value(analyst.sourceName()))
                .andExpect(jsonPath("$.items[0].created_by")
                        .value(analyst.userId().toString()))
                .andExpect(jsonPath("$.items[0].created_by_name")
                        .value(analyst.displayName()))
                .andExpect(jsonPath("$.items[0].created_at")
                        .value(START.toString()))
                .andExpect(jsonPath("$.items[0].secret_ref")
                        .doesNotExist())
                .andExpect(jsonPath("$.items[0].password_hash")
                        .doesNotExist());
    }

    @Test
    void analystAndViewerSeeOnlyOwnJobsIncludingTotal() throws Exception {
        for (var role : List.of(UserRole.ANALYST, UserRole.VIEWER)) {
            var tenant = createTenant();
            var owner = createContext(tenant, role);
            var other = createContext(tenant, UserRole.ANALYST);
            var beta = createContext(createTenant(), UserRole.ADMIN);

            var ownId = insertJob(
                    owner,
                    AnalysisJobStatus.RUNNING,
                    "销售分析",
                    START);

            insertJob(
                    other,
                    AnalysisJobStatus.RUNNING,
                    "销售分析",
                    START);

            insertJob(
                    beta,
                    AnalysisJobStatus.RUNNING,
                    "销售分析",
                    START);

            mockMvc.perform(get(PATH)
                            .header("Authorization", bearer(owner)))
                    .andExpect(status().isOk())
                    .andExpect(jsonPath("$.total").value(1))
                    .andExpect(jsonPath("$.items.length()").value(1))
                    .andExpect(jsonPath("$.items[0].id")
                            .value(ownId.toString()));

            mockMvc.perform(get(PATH)
                            .header("Authorization", bearer(owner))
                            .param("statuses", "RUNNING")
                            .param("keyword", "销售"))
                    .andExpect(status().isOk())
                    .andExpect(jsonPath("$.total").value(1))
                    .andExpect(jsonPath("$.items.length()").value(1))
                    .andExpect(jsonPath("$.items[0].id")
                            .value(ownId.toString()));
        }
    }

    @Test
    void paginatesWithStableOrderingAndKeepsTotalOnOutOfRangePage()
            throws Exception {

        var admin = createContext(createTenant(), UserRole.ADMIN);
        var ids = new ArrayList<String>();

        for (int index = 0; index < 3; index++) {
            ids.add(insertJob(
                    admin,
                    AnalysisJobStatus.CREATED,
                    "同一创建时间的任务",
                    START).toString());
        }

        ids.sort(Comparator.reverseOrder());

        mockMvc.perform(get(PATH)
                        .header("Authorization", bearer(admin))
                        .param("page", "1")
                        .param("size", "2"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.total").value(3))
                .andExpect(jsonPath("$.total_pages").value(2))
                .andExpect(jsonPath("$.items.length()").value(2))
                .andExpect(jsonPath("$.items[0].id").value(ids.get(0)))
                .andExpect(jsonPath("$.items[1].id").value(ids.get(1)));

        mockMvc.perform(get(PATH)
                        .header("Authorization", bearer(admin))
                        .param("page", "2")
                        .param("size", "2"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.total").value(3))
                .andExpect(jsonPath("$.items.length()").value(1))
                .andExpect(jsonPath("$.items[0].id").value(ids.get(2)));

        mockMvc.perform(get(PATH)
                        .header("Authorization", bearer(admin))
                        .param("page", "3")
                        .param("size", "2"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.total").value(3))
                .andExpect(jsonPath("$.items.length()").value(0));
    }

    @Test
    void combinesFiltersAndUsesHalfOpenTimeRange() throws Exception {
        var tenant = createTenant();
        var admin = createContext(tenant, UserRole.ADMIN);
        var otherSource = createContext(tenant, UserRole.ANALYST);

        var expected = insertJob(
                admin,
                AnalysisJobStatus.RUNNING,
                "华东销售分析",
                START);

        insertJob(
                admin,
                AnalysisJobStatus.RUNNING,
                "华东销售分析",
                START.minusSeconds(1));

        insertJob(
                admin,
                AnalysisJobStatus.RUNNING,
                "华东销售分析",
                END);

        insertJob(
                admin,
                AnalysisJobStatus.CREATED,
                "华东销售分析",
                START);

        insertJob(
                admin,
                AnalysisJobStatus.RUNNING,
                "库存分析",
                START);

        insertJob(
                otherSource,
                AnalysisJobStatus.RUNNING,
                "华东销售分析",
                START);

        mockMvc.perform(get(PATH)
                        .header("Authorization", bearer(admin))
                        .param("statuses", "RUNNING", "FAILED")
                        .param("keyword", " 销售 ")
                        .param("data_source_id", admin.sourceId().toString())
                        .param("created_from", "2026-10-01T08:00:00+08:00")
                        .param("created_to", END.toString()))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.total").value(1))
                .andExpect(jsonPath("$.items.length()").value(1))
                .andExpect(jsonPath("$.items[0].id")
                        .value(expected.toString()));
    }

    @Test
    void keywordSpecialCharactersRemainLiteralData() throws Exception {
        var admin = createContext(createTenant(), UserRole.ADMIN);

        var expected = insertJob(
                admin,
                AnalysisJobStatus.CREATED,
                "利润100%!_ ' OR 1=1 --",
                START);

        insertJob(
                admin,
                AnalysisJobStatus.CREATED,
                "普通销售分析",
                START);

        for (var keyword : List.of("100%!_", "' OR 1=1 --")) {
            mockMvc.perform(get(PATH)
                            .header("Authorization", bearer(admin))
                            .param("keyword", keyword))
                    .andExpect(status().isOk())
                    .andExpect(jsonPath("$.total").value(1))
                    .andExpect(jsonPath("$.items.length()").value(1))
                    .andExpect(jsonPath("$.items[0].id")
                            .value(expected.toString()));
        }
    }

    @Test
    void blankKeywordIsTreatedAsMissing() throws Exception {
        var admin = createContext(createTenant(), UserRole.ADMIN);

        insertJob(
                admin,
                AnalysisJobStatus.CREATED,
                "销售分析",
                START);

        mockMvc.perform(get(PATH)
                        .header("Authorization", bearer(admin))
                        .param("keyword", " \t "))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.total").value(1));
    }

    @Test
    void anotherTenantsDataSourceDoesNotRevealJobs() throws Exception {
        var admin = createContext(createTenant(), UserRole.ADMIN);
        var beta = createContext(createTenant(), UserRole.ADMIN);

        insertJob(
                admin,
                AnalysisJobStatus.CREATED,
                "本租户任务",
                START);

        insertJob(
                beta,
                AnalysisJobStatus.CREATED,
                "其他租户任务",
                START);

        mockMvc.perform(get(PATH)
                        .header("Authorization", bearer(admin))
                        .param("data_source_id", beta.sourceId().toString()))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.total").value(0))
                .andExpect(jsonPath("$.total_pages").value(0))
                .andExpect(jsonPath("$.items.length()").value(0));
    }

    @Test
    void invalidParametersReturn400() throws Exception {
        var admin = createContext(createTenant(), UserRole.ADMIN);

        var invalidParameters = List.of(
                Map.entry("page", "0"),
                Map.entry("page", "10001"),
                Map.entry("page", "2147483648"),
                Map.entry("page", "abc"),
                Map.entry("size", "0"),
                Map.entry("size", "101"),
                Map.entry("size", ""),
                Map.entry("statuses", ""),
                Map.entry("statuses", "UNKNOWN"),
                Map.entry("statuses", "RUNNING,FAILED"),
                Map.entry("data_source_id", "not-a-uuid"),
                Map.entry("data_source_id", "1-1-1-1-1"),
                Map.entry("created_from", "not-a-time"),
                Map.entry("created_to", "2026-10-01T00:00:00"),
                Map.entry("keyword", "x".repeat(201)));

        for (var parameter : invalidParameters) {
            mockMvc.perform(get(PATH)
                            .header("Authorization", bearer(admin))
                            .param(parameter.getKey(), parameter.getValue()))
                    .andExpect(status().isBadRequest())
                    .andExpect(jsonPath("$.code")
                            .value("INVALID_ANALYSIS_JOB_SEARCH"))
                    .andExpect(jsonPath("$.trace_id").isNotEmpty());
        }
    }

    @Test
    void rejectsReversedRangeAndDuplicateScalarParameters()
            throws Exception {

        var admin = createContext(createTenant(), UserRole.ADMIN);

        mockMvc.perform(get(PATH)
                        .header("Authorization", bearer(admin))
                        .param("created_from", END.toString())
                        .param("created_to", START.toString()))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.code")
                        .value("INVALID_ANALYSIS_JOB_SEARCH"));

        mockMvc.perform(get(PATH)
                        .header("Authorization", bearer(admin))
                        .param("page", "1", "2"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.code")
                        .value("INVALID_ANALYSIS_JOB_SEARCH"));
    }

    @Test
    void rejectsClientSuppliedPermissionAndSortParameters()
            throws Exception {

        var admin = createContext(createTenant(), UserRole.ADMIN);

        for (var parameter : List.of(
                "tenant_id", "created_by", "is_admin", "sort")) {

            mockMvc.perform(get(PATH)
                            .header("Authorization", bearer(admin))
                            .param(parameter, "anything"))
                    .andExpect(status().isBadRequest())
                    .andExpect(jsonPath("$.code")
                            .value("INVALID_ANALYSIS_JOB_SEARCH"));
        }
    }

    @Test
    void equalTimeBoundsReturnEmptyPage() throws Exception {
        var admin = createContext(createTenant(), UserRole.ADMIN);

        insertJob(
                admin,
                AnalysisJobStatus.CREATED,
                "边界任务",
                START);

        mockMvc.perform(get(PATH)
                        .header("Authorization", bearer(admin))
                        .param("created_from", START.toString())
                        .param("created_to", START.toString()))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.total").value(0))
                .andExpect(jsonPath("$.items.length()").value(0));
    }

    @Test
    void crossTenantAssociationsAreExcludedFromItemsAndTotal()
            throws Exception {

        var alpha = createContext(createTenant(), UserRole.ADMIN);
        var beta = createContext(createTenant(), UserRole.ADMIN);

        var wrongSourceJob = insertJob(
                alpha,
                AnalysisJobStatus.CREATED,
                "异常数据源关联",
                START);

        var wrongCreatorJob = insertJob(
                alpha,
                AnalysisJobStatus.CREATED,
                "异常创建人关联",
                START);

        // 故意构造外键合法、但租户关系错误的测试数据。
        jdbcTemplate.update(
                "UPDATE copilot.analysis_jobs SET data_source_id = ? WHERE id = ?",
                beta.sourceId(),
                wrongSourceJob);

        jdbcTemplate.update(
                "UPDATE copilot.analysis_jobs SET created_by = ? WHERE id = ?",
                beta.userId(),
                wrongCreatorJob);

        mockMvc.perform(get(PATH)
                        .header("Authorization", bearer(alpha)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.total").value(0))
                .andExpect(jsonPath("$.items.length()").value(0));
    }

    private Tenant createTenant() {
        return tenants.saveAndFlush(new Tenant(
                UUID.randomUUID(),
                "search-" + UUID.randomUUID(),
                "查询接口测试租户"));
    }

    private Context createContext(Tenant tenant, UserRole role) {
        String suffix = UUID.randomUUID().toString();
        String displayName = role.name() + "-用户-" + suffix;
        String sourceName = "数据源-" + suffix;

        var user = users.saveAndFlush(new AppUser(
                UUID.randomUUID(),
                tenant.getId(),
                suffix + "@example.test",
                "test-only-password-hash",
                displayName,
                Set.of(role)));

        var source = dataSources.saveAndFlush(new DataSource(
                UUID.randomUUID(),
                tenant.getId(),
                sourceName,
                "localhost",
                5432,
                "northwind",
                "northwind",
                "env:TEST_ONLY_PASSWORD"));

        return new Context(
                tenant.getId(),
                user.getId(),
                source.getId(),
                displayName,
                sourceName,
                role);
    }

    private UUID insertJob(
            Context context,
            AnalysisJobStatus jobStatus,
            String question,
            Instant createdAt) {

        UUID jobId = UUID.randomUUID();

        jdbcTemplate.update(
                """
                INSERT INTO copilot.analysis_jobs (
                    id, tenant_id, data_source_id, created_by,
                    question, status, idempotency_key,
                    request_hash, trace_id, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                jobId,
                context.tenantId(),
                context.sourceId(),
                context.userId(),
                question,
                jobStatus.name(),
                "search-" + jobId,
                "test-request-hash",
                "test-trace-" + jobId,
                Timestamp.from(createdAt),
                Timestamp.from(createdAt));

        return jobId;
    }

    private String bearer(Context context) {
        return "Bearer " + token(
                context,
                List.of(context.role().name()));
    }

    private String token(Context context, List<String> roles) {
        var now = Instant.now();

        var claims = JwtClaimsSet.builder()
                .issuer(securityProperties.jwtIssuer())
                .issuedAt(now)
                .expiresAt(now.plusSeconds(300))
                .subject(context.userId().toString())
                .claim("tenant_id", context.tenantId().toString())
                .claim("roles", roles)
                .build();

        var header = JwsHeader.with(MacAlgorithm.HS256).build();

        return jwtEncoder.encode(
                        JwtEncoderParameters.from(header, claims))
                .getTokenValue();
    }

    private record Context(
            UUID tenantId,
            UUID userId,
            UUID sourceId,
            String displayName,
            String sourceName,
            UserRole role) {}
}