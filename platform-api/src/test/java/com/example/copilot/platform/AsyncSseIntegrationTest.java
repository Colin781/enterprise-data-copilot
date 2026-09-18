package com.example.copilot.platform;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.asyncDispatch;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.request;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.example.copilot.PostgresRedisIntegrationTest;
import com.example.copilot.analysis.domain.AnalysisJob;
import com.example.copilot.analysis.domain.AnalysisJobStatus;
import com.example.copilot.analysis.repository.AgentStepRepository;
import com.example.copilot.analysis.repository.AnalysisJobRepository;
import com.example.copilot.approval.repository.ApprovalRepository;
import com.example.copilot.audit.repository.AuditEventRepository;
import com.example.copilot.datasource.domain.DataSource;
import com.example.copilot.datasource.repository.DataSourceRepository;
import com.example.copilot.events.AnalysisEventStreamService;
import com.example.copilot.execution.AnalysisJobDispatcher;
import com.example.copilot.identity.domain.AppUser;
import com.example.copilot.identity.domain.Tenant;
import com.example.copilot.identity.domain.UserRole;
import com.example.copilot.identity.repository.AppUserRepository;
import com.example.copilot.identity.repository.TenantRepository;
import com.example.copilot.integration.agent.AgentRunClient;
import com.example.copilot.integration.agent.AgentRunResult;
import java.time.Duration;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.Timeout;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.http.MediaType;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;
import tools.jackson.databind.ObjectMapper;

@SpringBootTest(properties = {"platform.execution.enabled=true", "platform.execution.max-attempts=3"})
@AutoConfigureMockMvc
class AsyncSseIntegrationTest extends PostgresRedisIntegrationTest {

    private static final String PASSWORD = "correct-horse-battery-staple";

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
    AgentStepRepository stepRepository;

    @Autowired
    ApprovalRepository approvalRepository;

    @Autowired
    AuditEventRepository auditRepository;

    @Autowired
    AnalysisEventStreamService eventStream;

    @Autowired
    AnalysisJobDispatcher dispatcher;

    @Autowired
    StringRedisTemplate redis;

    @MockitoBean
    AgentRunClient agentRunClient;

    @BeforeEach
    void cleanState() {
        stepRepository.deleteAllInBatch();
        approvalRepository.deleteAllInBatch();
        auditRepository.deleteAllInBatch();
        jobRepository.deleteAllInBatch();
        dataSourceRepository.deleteAllInBatch();
        userRepository.deleteAllInBatch();
        tenantRepository.deleteAllInBatch();
        redis.getConnectionFactory().getConnection().serverCommands().flushDb();
    }

    @Test
    @Timeout(10)
    void createReturnsBeforeAgentCompletesAndRedisReplaysOrderedProgressWhilePostgresKeepsFinalState()
            throws Exception {
        var tenant = tenantRepository.save(new Tenant(UUID.randomUUID(), "alpha", "Alpha"));
        var analyst = userRepository.save(new AppUser(
                UUID.randomUUID(),
                tenant.getId(),
                "analyst@alpha.test",
                passwordEncoder.encode(PASSWORD),
                "Analyst",
                Set.of(UserRole.ANALYST)));
        var source = dataSourceRepository.save(new DataSource(
                UUID.randomUUID(),
                tenant.getId(),
                "northwind",
                "business-db",
                5432,
                "northwind",
                "northwind",
                "env:BUSINESS_DB_READONLY_PASSWORD"));
        var enteredAgent = new CountDownLatch(1);
        var releaseAgent = new CountDownLatch(1);
        var attempts = new AtomicInteger();
        when(agentRunClient.start(any(), any(), any(), any(), any(), any(), any(), any()))
                .thenAnswer(invocation -> {
                    if (attempts.incrementAndGet() == 1) {
                        throw new IllegalStateException("temporary agent outage");
                    }
                    enteredAgent.countDown();
                    assertThat(releaseAgent.await(3, TimeUnit.SECONDS)).isTrue();
                    var jobId = invocation.getArgument(0, UUID.class);
                    return new AgentRunResult(
                            jobId.toString(),
                            "COMPLETED",
                            objectMapper.readTree(
                                    """
                                    {
                                      "sql":"SELECT 1 AS value",
                                      "answer":"one row",
                                      "error_code":null,
                                      "columns":["label","value"],
                                      "rows":[{"label":"result","value":1}],
                                      "chart_spec":{"type":"bar","title":"Result","x":"label","series":["value"]},
                                      "citations":[{"document_title":"Revenue","section_title":"Definition"}]
                                    }
                                    """));
                });
        var token = login();

        var started = System.nanoTime();
        var response = mockMvc.perform(post("/api/analysis/jobs")
                        .header("Authorization", "Bearer " + token)
                        .header("Idempotency-Key", "p8-async-request-0001")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"data_source_id\":\"%s\",\"question\":\"sales by month\"}"
                                .formatted(source.getId())))
                .andExpect(status().isAccepted())
                .andReturn();
        var responseTime = Duration.ofNanos(System.nanoTime() - started);
        var jobId = UUID.fromString(objectMapper
                .readTree(response.getResponse().getContentAsString())
                .get("id")
                .asText());

        assertThat(responseTime).isLessThan(Duration.ofSeconds(1));
        assertThat(enteredAgent.await(2, TimeUnit.SECONDS)).isTrue();
        assertThat(attempts).hasValue(2);
        assertThat(jobRepository.findById(jobId).orElseThrow().getStatus()).isEqualTo(AnalysisJobStatus.PLANNING);

        releaseAgent.countDown();
        awaitStatus(jobId, AnalysisJobStatus.COMPLETED);

        var persisted = jobRepository.findById(jobId).orElseThrow();
        assertThat(persisted.getGeneratedSql()).isEqualTo("SELECT 1 AS value");
        assertThat(persisted.getAnswer()).isEqualTo("one row");
        assertThat(persisted.getResultRowsJson()).contains("result");
        assertThat(persisted.getFinishedAt()).isNotNull();

        mockMvc.perform(get("/api/analysis/jobs/{jobId}", jobId).header("Authorization", "Bearer " + token))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.columns[1]").value("value"))
                .andExpect(jsonPath("$.rows[0].value").value(1))
                .andExpect(jsonPath("$.chart.type").value("bar"))
                .andExpect(jsonPath("$.citations[0].document_title").value("Revenue"));
        mockMvc.perform(get("/api/analysis/jobs").header("Authorization", "Bearer " + token))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$[0].id").value(jobId.toString()));

        var events = eventStream.replay(jobId, null);
        assertThat(events).hasSizeGreaterThanOrEqualTo(3);
        assertThat(events).extracting(event -> event.sequence()).isSorted().doesNotHaveDuplicates();
        assertThat(events)
                .extracting(event -> event.status())
                .contains(AnalysisJobStatus.CREATED, AnalysisJobStatus.PLANNING, AnalysisJobStatus.COMPLETED);

        var disconnectedAfter = events.get(0);
        var replayed = eventStream.replay(jobId, disconnectedAfter.eventId().toString());
        assertThat(replayed).containsExactlyElementsOf(events.subList(1, events.size()));
        assertThat(replayed).allMatch(event -> event.sequence() > disconnectedAfter.sequence());

        redis.getConnectionFactory().getConnection().serverCommands().flushDb();
        var afterRedisLoss = jobRepository.findById(jobId).orElseThrow();
        assertThat(afterRedisLoss.getStatus()).isEqualTo(AnalysisJobStatus.COMPLETED);
        assertThat(afterRedisLoss.getAnswer()).isEqualTo("one row");

        var snapshotStream = mockMvc.perform(get("/api/analysis/jobs/{jobId}/events", jobId)
                        .header("Authorization", "Bearer " + token)
                        .header("Last-Event-ID", disconnectedAfter.eventId()))
                .andExpect(status().isOk())
                .andExpect(request().asyncStarted())
                .andReturn();
        mockMvc.perform(asyncDispatch(snapshotStream))
                .andExpect(status().isOk())
                .andExpect(content().string(org.hamcrest.Matchers.containsString("JOB_SNAPSHOT")))
                .andExpect(content().string(org.hamcrest.Matchers.containsString("postgresql")));
    }

    @Test
    @Timeout(10)
    void startupRecoveryRedispatchesPostgresJobsWithTheSameStableJobId() throws Exception {
        var tenant = tenantRepository.save(new Tenant(UUID.randomUUID(), "recovery", "Recovery"));
        var analyst = userRepository.save(new AppUser(
                UUID.randomUUID(),
                tenant.getId(),
                "analyst@recovery.test",
                passwordEncoder.encode(PASSWORD),
                "Analyst",
                Set.of(UserRole.ANALYST)));
        var source = dataSourceRepository.save(new DataSource(
                UUID.randomUUID(),
                tenant.getId(),
                "northwind-recovery",
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
                "recover this task",
                "p8-recovery-request-0001",
                "0".repeat(64),
                "1".repeat(32)));
        when(agentRunClient.start(any(), any(), any(), any(), any(), any(), any(), any()))
                .thenReturn(new AgentRunResult(
                        job.getId().toString(), "COMPLETED", objectMapper.readTree("{\"answer\":\"recovered\"}")));

        dispatcher.recoverUnfinishedJobs();

        awaitStatus(job.getId(), AnalysisJobStatus.COMPLETED);
        var persisted = jobRepository.findById(job.getId()).orElseThrow();
        assertThat(persisted.getWorkflowThreadId()).isEqualTo(job.getId().toString());
        assertThat(persisted.getAnswer()).isEqualTo("recovered");
        assertThat(eventStream.replay(job.getId(), null))
                .extracting(event -> event.type())
                .contains("JOB_RECOVERED", "JOB_STATUS_CHANGED");
    }

    private String login() throws Exception {
        var result = mockMvc.perform(post("/api/auth/login")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(
                                """
                                {"tenant_slug":"alpha","email":"analyst@alpha.test","password":"%s"}
                                """
                                        .formatted(PASSWORD)))
                .andExpect(status().isOk())
                .andReturn();
        return objectMapper
                .readTree(result.getResponse().getContentAsString())
                .get("access_token")
                .asText();
    }

    private void awaitStatus(UUID jobId, AnalysisJobStatus expected) throws InterruptedException {
        var deadline = System.nanoTime() + Duration.ofSeconds(4).toNanos();
        while (System.nanoTime() < deadline) {
            if (jobRepository.findById(jobId).orElseThrow().getStatus() == expected) {
                return;
            }
            Thread.sleep(Duration.ofMillis(25));
        }
        assertThat(jobRepository.findById(jobId).orElseThrow().getStatus()).isEqualTo(expected);
    }
}
