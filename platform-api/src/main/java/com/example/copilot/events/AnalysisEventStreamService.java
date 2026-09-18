package com.example.copilot.events;

import com.example.copilot.analysis.api.AnalysisJobResource;
import com.example.copilot.analysis.domain.AnalysisJobStateMachine;
import com.example.copilot.execution.AnalysisExecutionProperties;
import java.io.IOException;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.CopyOnWriteArrayList;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.dao.DataAccessException;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Service;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

@Service
public class AnalysisEventStreamService {

    private static final Logger LOGGER = LoggerFactory.getLogger(AnalysisEventStreamService.class);

    private final RedisAnalysisEventStore eventStore;
    private final AnalysisExecutionProperties properties;
    private final ConcurrentHashMap<UUID, Object> jobLocks = new ConcurrentHashMap<>();
    private final ConcurrentHashMap<UUID, CopyOnWriteArrayList<SseEmitter>> subscribers = new ConcurrentHashMap<>();

    public AnalysisEventStreamService(RedisAnalysisEventStore eventStore, AnalysisExecutionProperties properties) {
        this.eventStore = eventStore;
        this.properties = properties;
    }

    public AnalysisJobEvent publish(JobProgressSignal signal) {
        synchronized (lock(signal.jobId())) {
            AnalysisJobEvent event;
            try {
                event = eventStore.append(signal);
            } catch (DataAccessException | IllegalStateException exception) {
                LOGGER.warn(
                        "Redis progress append failed for job {}; PostgreSQL remains authoritative", signal.jobId());
                event = transientEvent(signal);
            }
            broadcast(event);
            return event;
        }
    }

    public List<AnalysisJobEvent> replay(UUID jobId, String lastEventId) {
        synchronized (lock(jobId)) {
            var events = safeRead(jobId);
            if (lastEventId == null || lastEventId.isBlank()) {
                return events;
            }
            for (var index = 0; index < events.size(); index++) {
                if (events.get(index).eventId().toString().equals(lastEventId)) {
                    return List.copyOf(events.subList(index + 1, events.size()));
                }
            }
            return List.of();
        }
    }

    public SseEmitter subscribe(AnalysisJobResource snapshot, UUID tenantId, String lastEventId) {
        var jobId = snapshot.id();
        var emitter = new SseEmitter(properties.sseTimeout().toMillis());
        synchronized (lock(jobId)) {
            var events = safeRead(jobId);
            var replay = after(events, lastEventId);
            subscribers
                    .computeIfAbsent(jobId, ignored -> new CopyOnWriteArrayList<>())
                    .add(emitter);
            onClose(jobId, emitter);
            try {
                if (events.isEmpty()
                        || (lastEventId != null
                                && !lastEventId.isBlank()
                                && replay.isEmpty()
                                && !contains(events, lastEventId))) {
                    send(emitter, snapshotEvent(snapshot, tenantId));
                } else {
                    for (var event : replay) {
                        send(emitter, event);
                    }
                }
                if (new AnalysisJobStateMachine().isTerminal(snapshot.status())) {
                    remove(jobId, emitter);
                    emitter.complete();
                }
            } catch (IOException exception) {
                remove(jobId, emitter);
                emitter.completeWithError(exception);
            }
        }
        return emitter;
    }

    private List<AnalysisJobEvent> safeRead(UUID jobId) {
        try {
            return eventStore.readAll(jobId);
        } catch (DataAccessException | IllegalStateException exception) {
            LOGGER.warn("Redis progress replay failed for job {}; PostgreSQL snapshot will be used", jobId);
            return List.of();
        }
    }

    private void broadcast(AnalysisJobEvent event) {
        var current = new ArrayList<>(subscribers.getOrDefault(event.jobId(), new CopyOnWriteArrayList<>()));
        for (var emitter : current) {
            try {
                send(emitter, event);
                if (new AnalysisJobStateMachine().isTerminal(event.status())) {
                    remove(event.jobId(), emitter);
                    emitter.complete();
                }
            } catch (IOException exception) {
                remove(event.jobId(), emitter);
                emitter.completeWithError(exception);
            }
        }
    }

    private static void send(SseEmitter emitter, AnalysisJobEvent event) throws IOException {
        emitter.send(SseEmitter.event()
                .id(event.eventId().toString())
                .name(event.type())
                .data(event, MediaType.APPLICATION_JSON));
    }

    private void onClose(UUID jobId, SseEmitter emitter) {
        emitter.onCompletion(() -> remove(jobId, emitter));
        emitter.onTimeout(() -> remove(jobId, emitter));
        emitter.onError(ignored -> remove(jobId, emitter));
    }

    private void remove(UUID jobId, SseEmitter emitter) {
        var current = subscribers.get(jobId);
        if (current != null) {
            current.remove(emitter);
            if (current.isEmpty()) {
                subscribers.remove(jobId, current);
            }
        }
    }

    private Object lock(UUID jobId) {
        return jobLocks.computeIfAbsent(jobId, ignored -> new Object());
    }

    private static List<AnalysisJobEvent> after(List<AnalysisJobEvent> events, String lastEventId) {
        if (lastEventId == null || lastEventId.isBlank()) {
            return events;
        }
        for (var index = 0; index < events.size(); index++) {
            if (events.get(index).eventId().toString().equals(lastEventId)) {
                return List.copyOf(events.subList(index + 1, events.size()));
            }
        }
        return List.of();
    }

    private static boolean contains(List<AnalysisJobEvent> events, String eventId) {
        return events.stream().anyMatch(event -> event.eventId().toString().equals(eventId));
    }

    private static AnalysisJobEvent transientEvent(JobProgressSignal signal) {
        return new AnalysisJobEvent(
                "1.0",
                UUID.randomUUID(),
                0,
                signal.jobId(),
                signal.tenantId(),
                signal.traceId(),
                signal.type(),
                signal.status(),
                Instant.now(),
                Map.copyOf(signal.payload()));
    }

    private static AnalysisJobEvent snapshotEvent(AnalysisJobResource snapshot, UUID tenantId) {
        return new AnalysisJobEvent(
                "1.0",
                UUID.randomUUID(),
                snapshot.version(),
                snapshot.id(),
                tenantId,
                snapshot.traceId(),
                "JOB_SNAPSHOT",
                snapshot.status(),
                Instant.now(),
                Map.of("source", "postgresql", "replay_available", false));
    }
}
