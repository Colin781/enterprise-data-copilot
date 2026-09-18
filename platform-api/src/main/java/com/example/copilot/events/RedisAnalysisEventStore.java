package com.example.copilot.events;

import com.example.copilot.analysis.domain.AnalysisJobStatus;
import com.example.copilot.execution.AnalysisExecutionProperties;
import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.springframework.data.domain.Range;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.core.script.DefaultRedisScript;
import org.springframework.stereotype.Component;
import tools.jackson.core.type.TypeReference;
import tools.jackson.databind.ObjectMapper;

@Component
public class RedisAnalysisEventStore {

    private static final String APPEND_SCRIPT =
            """
            local sequence = redis.call('INCR', KEYS[1])
            redis.call('EXPIRE', KEYS[1], ARGV[1])
            redis.call('XADD', KEYS[2], 'MAXLEN', '=', ARGV[2], '*',
                'event_version', '1.0',
                'event_id', ARGV[3],
                'sequence', tostring(sequence),
                'job_id', ARGV[4],
                'tenant_id', ARGV[5],
                'trace_id', ARGV[6],
                'type', ARGV[7],
                'status', ARGV[8],
                'occurred_at', ARGV[9],
                'payload', ARGV[10])
            redis.call('EXPIRE', KEYS[2], ARGV[1])
            return sequence
            """;

    private static final TypeReference<Map<String, Object>> PAYLOAD_TYPE = new TypeReference<>() {};

    private final StringRedisTemplate redis;
    private final ObjectMapper objectMapper;
    private final AnalysisExecutionProperties properties;
    private final DefaultRedisScript<Long> appendScript = new DefaultRedisScript<>(APPEND_SCRIPT, Long.class);

    public RedisAnalysisEventStore(
            StringRedisTemplate redis, ObjectMapper objectMapper, AnalysisExecutionProperties properties) {
        this.redis = redis;
        this.objectMapper = objectMapper;
        this.properties = properties;
    }

    public AnalysisJobEvent append(JobProgressSignal signal) {
        var eventId = UUID.randomUUID();
        var occurredAt = Instant.now();
        var sequence = redis.execute(
                appendScript,
                List.of(sequenceKey(signal.jobId()), streamKey(signal.jobId())),
                Long.toString(properties.eventRetention().toSeconds()),
                Integer.toString(properties.eventMaxLength()),
                eventId.toString(),
                signal.jobId().toString(),
                signal.tenantId().toString(),
                signal.traceId(),
                signal.type(),
                signal.status().name(),
                occurredAt.toString(),
                objectMapper.writeValueAsString(signal.payload()));
        if (sequence == null) {
            throw new IllegalStateException("Redis did not return an event sequence");
        }
        return new AnalysisJobEvent(
                "1.0",
                eventId,
                sequence,
                signal.jobId(),
                signal.tenantId(),
                signal.traceId(),
                signal.type(),
                signal.status(),
                occurredAt,
                Map.copyOf(signal.payload()));
    }

    public List<AnalysisJobEvent> readAll(UUID jobId) {
        return redis.opsForStream().range(streamKey(jobId), Range.unbounded()).stream()
                .map(record -> {
                    var values = record.getValue();
                    return new AnalysisJobEvent(
                            text(values, "event_version"),
                            UUID.fromString(text(values, "event_id")),
                            Long.parseLong(text(values, "sequence")),
                            UUID.fromString(text(values, "job_id")),
                            UUID.fromString(text(values, "tenant_id")),
                            text(values, "trace_id"),
                            text(values, "type"),
                            AnalysisJobStatus.valueOf(text(values, "status")),
                            Instant.parse(text(values, "occurred_at")),
                            objectMapper.readValue(text(values, "payload"), PAYLOAD_TYPE));
                })
                .toList();
    }

    private static String text(Map<Object, Object> values, String key) {
        var value = values.get(key);
        if (value == null) {
            throw new IllegalStateException("Redis event is missing field " + key);
        }
        return value.toString();
    }

    private static String streamKey(UUID jobId) {
        return "analysis:events:" + jobId;
    }

    private static String sequenceKey(UUID jobId) {
        return "analysis:sequence:" + jobId;
    }
}
