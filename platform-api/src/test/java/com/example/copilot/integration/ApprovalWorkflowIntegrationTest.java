package com.example.copilot.integration;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.example.copilot.client.agent.AgentResumeResult;
import com.example.copilot.client.agent.AgentRunClient;
import com.example.copilot.dto.request.InternalApprovalRequest;
import com.example.copilot.entity.AnalysisJob;
import com.example.copilot.entity.AppUser;
import com.example.copilot.entity.DataSource;
import com.example.copilot.entity.Tenant;
import com.example.copilot.enums.AnalysisJobStatus;
import com.example.copilot.enums.ApprovalStatus;
import com.example.copilot.enums.UserRole;
import com.example.copilot.exception.ApprovalAlreadyDecidedException;
import com.example.copilot.repository.AgentStepRepository;
import com.example.copilot.repository.AnalysisJobRepository;
import com.example.copilot.repository.AppUserRepository;
import com.example.copilot.repository.ApprovalRepository;
import com.example.copilot.repository.AuditEventRepository;
import com.example.copilot.repository.DataSourceRepository;
import com.example.copilot.repository.TenantRepository;
import com.example.copilot.security.CallerIdentity.Caller;
import com.example.copilot.service.ApprovalService;
import com.example.copilot.support.PostgresIntegrationTest;
import java.util.List;
import java.util.Set;
import java.util.UUID;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.bean.override.mockito.MockitoBean;

@SpringBootTest
class ApprovalWorkflowIntegrationTest extends PostgresIntegrationTest {

    @Autowired
    ApprovalService approvalService;

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
    AgentStepRepository stepRepository;

    @Autowired
    AuditEventRepository auditRepository;

    @MockitoBean
    AgentRunClient agentRunClient;

    @BeforeEach
    void cleanDatabase() {
        stepRepository.deleteAllInBatch();
        approvalRepository.deleteAllInBatch();
        auditRepository.deleteAllInBatch();
        jobRepository.deleteAllInBatch();
        dataSourceRepository.deleteAllInBatch();
        userRepository.deleteAllInBatch();
        tenantRepository.deleteAllInBatch();
    }

    @Test
    void administratorDecisionResumesOnceAndDuplicateApprovalIsRejected() {
        var tenant = tenantRepository.save(new Tenant(UUID.randomUUID(), "alpha", "Alpha"));
        var analyst = userRepository.save(new AppUser(
                UUID.randomUUID(),
                tenant.getId(),
                "analyst@alpha.test",
                "not-used",
                "Analyst",
                Set.of(UserRole.ANALYST)));
        var admin = userRepository.save(new AppUser(
                UUID.randomUUID(), tenant.getId(), "admin@alpha.test", "not-used", "Admin", Set.of(UserRole.ADMIN)));
        var source = dataSourceRepository.save(new DataSource(
                UUID.randomUUID(),
                tenant.getId(),
                "northwind",
                "business-db",
                5432,
                "northwind",
                "northwind",
                "env:BUSINESS_DB_READONLY_PASSWORD"));
        var job = jobRepository.save(new AnalysisJob(
                UUID.randomUUID(),
                tenant.getId(),
                source.getId(),
                analyst.getId(),
                "sales by month",
                "approval-test-key",
                "0".repeat(64),
                "1".repeat(32)));
        var pending = approvalService.request(
                job.getId(),
                new InternalApprovalRequest(List.of("TOTAL_COST_LIMIT_EXCEEDED"), "sha256:" + "a".repeat(64)),
                "1".repeat(32));
        when(agentRunClient.resume(
                        eq(job.getId()),
                        eq(tenant.getId()),
                        eq(pending.id()),
                        eq(admin.getId()),
                        eq("approved"),
                        any(),
                        any()))
                .thenReturn(new AgentResumeResult(job.getId().toString(), "COMPLETED"));
        var caller = new Caller(admin.getId(), tenant.getId(), Set.of("ADMIN"));

        var approved =
                approvalService.decide(pending.id(), ApprovalStatus.APPROVED, "within budget", caller, "2".repeat(32));

        assertThat(approved.status()).isEqualTo("APPROVED");
        assertThat(jobRepository.findById(job.getId()).orElseThrow().getStatus())
                .isEqualTo(AnalysisJobStatus.COMPLETED);
        assertThatThrownBy(() -> approvalService.decide(
                        pending.id(), ApprovalStatus.APPROVED, "duplicate", caller, "3".repeat(32)))
                .isInstanceOf(ApprovalAlreadyDecidedException.class);
        verify(agentRunClient, times(1))
                .resume(
                        eq(job.getId()),
                        eq(tenant.getId()),
                        eq(pending.id()),
                        eq(admin.getId()),
                        eq("approved"),
                        any(),
                        any());
    }
}
