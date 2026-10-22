package com.example.copilot.integration;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.example.copilot.dto.request.AnalysisJobSearchCriteria;
import com.example.copilot.dto.response.AnalysisJobQueryRow;
import com.example.copilot.entity.AppUser;
import com.example.copilot.entity.DataSource;
import com.example.copilot.entity.Tenant;
import com.example.copilot.enums.AnalysisJobStatus;
import com.example.copilot.enums.UserRole;
import com.example.copilot.mapper.AnalysisJobQueryMapper;
import com.example.copilot.repository.AppUserRepository;
import com.example.copilot.repository.DataSourceRepository;
import com.example.copilot.repository.TenantRepository;
import com.example.copilot.support.PostgresIntegrationTest;
import java.sql.Timestamp;
import java.time.Instant;
import java.util.List;
import java.util.Set;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;

@SpringBootTest(properties = {
        "platform.execution.enabled=false",
        "platform.bootstrap.enabled=false"
})
class AnalysisJobDynamicQueryIntegrationTest extends PostgresIntegrationTest {

    private static final Instant START =
            Instant.parse("2026-10-01T00:00:00Z");

    private static final Instant END = START.plusSeconds(3600);

    @Autowired
    AnalysisJobQueryMapper mapper;

    @Autowired
    TenantRepository tenants;

    @Autowired
    AppUserRepository users;

    @Autowired
    DataSourceRepository dataSources;

    @Autowired
    JdbcTemplate jdbcTemplate;

    @Test
    void missingFiltersStillRestrictResultsToCurrentTenant() {
        var alpha = createContext();
        var beta = createContext();

        var first = insertJob(
                alpha, AnalysisJobStatus.CREATED, "销售分析", START);

        var second = insertJob(
                alpha, AnalysisJobStatus.RUNNING, "库存分析", END);

        insertJob(
                beta, AnalysisJobStatus.CREATED, "其他租户任务", START);

        var criteria = new AnalysisJobSearchCriteria(
                null, null, null, null);

        var rows = mapper.search(alpha.tenantId(), criteria);

        assertThat(rows)
                .extracting(AnalysisJobQueryRow::getId)
                .containsExactlyInAnyOrder(first, second);
    }

    @Test
    void filtersByMultipleStatuses() {
        var context = createContext();

        insertJob(
                context, AnalysisJobStatus.CREATED, "等待处理", START);

        var running = insertJob(
                context, AnalysisJobStatus.RUNNING, "正在执行", START);

        var failed = insertJob(
                context, AnalysisJobStatus.FAILED, "执行失败", START);

        var criteria = new AnalysisJobSearchCriteria(
                List.of(
                        AnalysisJobStatus.RUNNING,
                        AnalysisJobStatus.FAILED),
                null,
                null,
                null);

        var rows = mapper.search(context.tenantId(), criteria);

        assertThat(rows)
                .extracting(AnalysisJobQueryRow::getId)
                .containsExactlyInAnyOrder(running, failed);
    }

    @Test
    void combinesFiltersAndUsesInclusiveStartExclusiveEnd() {
        var context = createContext();

        var expected = insertJob(
                context,
                AnalysisJobStatus.RUNNING,
                "华东销售分析",
                START);

        insertJob(
                context,
                AnalysisJobStatus.RUNNING,
                "华东销售分析",
                START.minusSeconds(1));

        insertJob(
                context,
                AnalysisJobStatus.RUNNING,
                "华东销售分析",
                END);

        insertJob(
                context,
                AnalysisJobStatus.FAILED,
                "华东销售分析",
                START.plusSeconds(60));

        insertJob(
                context,
                AnalysisJobStatus.RUNNING,
                "库存分析",
                START.plusSeconds(60));

        var criteria = new AnalysisJobSearchCriteria(
                List.of(AnalysisJobStatus.RUNNING),
                "销售",
                START,
                END);

        var rows = mapper.search(context.tenantId(), criteria);

        assertThat(rows)
                .extracting(AnalysisJobQueryRow::getId)
                .containsExactly(expected);
    }

    @Test
    void treatsBlankKeywordAsMissing() {
        var context = createContext();

        var first = insertJob(
                context, AnalysisJobStatus.CREATED, "销售分析", START);

        var second = insertJob(
                context, AnalysisJobStatus.CREATED, "库存分析", END);

        var criteria = new AnalysisJobSearchCriteria(
                null, " \t ", null, null);

        assertThat(criteria.keyword()).isNull();

        assertThat(mapper.search(context.tenantId(), criteria))
                .extracting(AnalysisJobQueryRow::getId)
                .containsExactlyInAnyOrder(first, second);
    }

    @Test
    void treatsPercentUnderscoreAndEscapeCharacterAsLiteralText() {
        var context = createContext();

        var expected = insertJob(
                context,
                AnalysisJobStatus.CREATED,
                "完成率100%!_达标",
                START);

        insertJob(
                context,
                AnalysisJobStatus.CREATED,
                "完成率100AB达标",
                START);

        var criteria = new AnalysisJobSearchCriteria(
                null, "100%!_", null, null);

        var rows = mapper.search(context.tenantId(), criteria);

        assertThat(rows)
                .extracting(AnalysisJobQueryRow::getId)
                .containsExactly(expected);
    }

    @Test
    void rejectsEmptyStatusList() {
        assertThatThrownBy(() -> new AnalysisJobSearchCriteria(
                List.<AnalysisJobStatus>of(),
                null,
                null,
                null))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("statuses");
    }

    @Test
    void rejectsReversedTimeRange() {
        assertThatThrownBy(() -> new AnalysisJobSearchCriteria(
                null,
                null,
                END,
                START))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("createdFrom");
    }

    @Test
    void supportsOneSidedAndEqualTimeBounds() {
        var context = createContext();

        var first = insertJob(
                context, AnalysisJobStatus.CREATED, "第一条", START);

        var second = insertJob(
                context, AnalysisJobStatus.CREATED, "第二条", END);

        var onlyFrom = new AnalysisJobSearchCriteria(
                null, null, END, null);

        assertThat(mapper.search(context.tenantId(), onlyFrom))
                .extracting(AnalysisJobQueryRow::getId)
                .containsExactly(second);

        var onlyTo = new AnalysisJobSearchCriteria(
                null, null, null, END);

        assertThat(mapper.search(context.tenantId(), onlyTo))
                .extracting(AnalysisJobQueryRow::getId)
                .containsExactly(first);

        var equalBounds = new AnalysisJobSearchCriteria(
                null, null, END, END);

        assertThat(mapper.search(context.tenantId(), equalBounds))
                .isEmpty();
    }

    private Context createContext() {
        var tenant = tenants.saveAndFlush(new Tenant(
                UUID.randomUUID(),
                "dynamic-" + UUID.randomUUID(),
                "动态查询测试租户"));

        var user = users.saveAndFlush(new AppUser(
                UUID.randomUUID(),
                tenant.getId(),
                "student@example.test",
                "test-only-password-hash",
                "学习用户",
                Set.of(UserRole.ANALYST)));

        var source = dataSources.saveAndFlush(new DataSource(
                UUID.randomUUID(),
                tenant.getId(),
                "学习数据源",
                "localhost",
                5432,
                "northwind",
                "northwind",
                "env:TEST_ONLY_PASSWORD"));

        return new Context(
                tenant.getId(),
                user.getId(),
                source.getId());
    }

    private UUID insertJob(
            Context context,
            AnalysisJobStatus status,
            String question,
            Instant createdAt) {

        UUID jobId = UUID.randomUUID();

        // 仅用于构造测试数据，精确指定任务状态和创建时间。
        jdbcTemplate.update(
                """
                INSERT INTO copilot.analysis_jobs (
                    id,
                    tenant_id,
                    data_source_id,
                    created_by,
                    question,
                    status,
                    idempotency_key,
                    request_hash,
                    trace_id,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                jobId,
                context.tenantId(),
                context.sourceId(),
                context.userId(),
                question,
                status.name(),
                "dynamic-" + jobId,
                "test-request-hash",
                "test-trace-" + jobId,
                Timestamp.from(createdAt),
                Timestamp.from(createdAt));

        return jobId;
    }

    private record Context(
            UUID tenantId,
            UUID userId,
            UUID sourceId) {}
}