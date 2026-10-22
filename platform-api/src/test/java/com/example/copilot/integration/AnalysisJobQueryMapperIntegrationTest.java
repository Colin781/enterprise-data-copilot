package com.example.copilot.integration;

import static org.assertj.core.api.Assertions.assertThat;

import com.example.copilot.entity.AnalysisJob;
import com.example.copilot.entity.AppUser;
import com.example.copilot.entity.DataSource;
import com.example.copilot.entity.Tenant;
import com.example.copilot.enums.UserRole;
import com.example.copilot.mapper.AnalysisJobQueryMapper;
import com.example.copilot.repository.AnalysisJobRepository;
import com.example.copilot.repository.AppUserRepository;
import com.example.copilot.repository.DataSourceRepository;
import com.example.copilot.repository.TenantRepository;
import com.example.copilot.support.PostgresIntegrationTest;
import java.util.Set;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;

@SpringBootTest(properties = {"platform.execution.enabled=false", "platform.bootstrap.enabled=false"})
class AnalysisJobQueryMapperIntegrationTest extends PostgresIntegrationTest {

    @Autowired
    AnalysisJobQueryMapper mapper;

    @Autowired
    TenantRepository tenants;

    @Autowired
    AppUserRepository users;

    @Autowired
    DataSourceRepository dataSources;

    @Autowired
    AnalysisJobRepository jobs;

    @Test
    void findsJobWithinItsTenantAndMapsAllFields() {
        var fixture = createFixture();

        var row = mapper.findByTenantIdAndId(fixture.tenantId(), fixture.jobId());

        assertThat(row).isNotNull();
        assertThat(row.getId()).isEqualTo(fixture.jobId());
        assertThat(row.getQuestion()).isEqualTo("按月统计销售额");
        assertThat(row.getStatus()).isEqualTo("CREATED");
    }

    @Test
    void anotherTenantCannotReadTheJob() {
        var alpha = createFixture();
        var beta = createFixture();

        var ownJob = mapper.findByTenantIdAndId(beta.tenantId(), beta.jobId());

        var otherTenantsJob = mapper.findByTenantIdAndId(beta.tenantId(), alpha.jobId());

        assertThat(ownJob).isNotNull();
        assertThat(otherTenantsJob).isNull();
    }

    @Test
    void returnsNullWhenJobDoesNotExist() {
        var fixture = createFixture();

        var row = mapper.findByTenantIdAndId(fixture.tenantId(), UUID.randomUUID());

        assertThat(row).isNull();
    }

    private Fixture createFixture() {
        var tenant =
                tenants.saveAndFlush(new Tenant(UUID.randomUUID(), "mybatis-" + UUID.randomUUID(), "MyBatis 学习租户"));

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

        var job = jobs.saveAndFlush(new AnalysisJob(
                UUID.randomUUID(),
                tenant.getId(),
                source.getId(),
                user.getId(),
                "按月统计销售额",
                "mybatis-learning-" + UUID.randomUUID(),
                "test-request-hash",
                "test-trace-" + UUID.randomUUID()));

        return new Fixture(tenant.getId(), job.getId());
    }

    private record Fixture(UUID tenantId, UUID jobId) {}
}
