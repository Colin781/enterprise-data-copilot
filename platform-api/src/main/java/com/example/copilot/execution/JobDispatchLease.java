package com.example.copilot.execution;

import java.time.Duration;
import java.util.List;
import java.util.UUID;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.core.script.DefaultRedisScript;
import org.springframework.stereotype.Component;

@Component
public class JobDispatchLease {

    private static final Logger LOGGER = LoggerFactory.getLogger(JobDispatchLease.class);
    private static final DefaultRedisScript<Long> RELEASE_SCRIPT = new DefaultRedisScript<>(
            "if redis.call('GET', KEYS[1]) == ARGV[1] then return redis.call('DEL', KEYS[1]) else return 0 end",
            Long.class);

    private final StringRedisTemplate redis;
    private final Duration leaseDuration;

    public JobDispatchLease(StringRedisTemplate redis, AnalysisExecutionProperties properties) {
        this.redis = redis;
        this.leaseDuration = properties.dispatchLease();
    }

    public boolean acquire(UUID jobId, String owner) {
        try {
            return Boolean.TRUE.equals(redis.opsForValue().setIfAbsent(key(jobId), owner, leaseDuration));
        } catch (RuntimeException exception) {
            LOGGER.warn("Redis dispatch lease unavailable for job {}; continuing with PostgreSQL idempotency", jobId);
            return true;
        }
    }

    public void release(UUID jobId, String owner) {
        try {
            redis.execute(RELEASE_SCRIPT, List.of(key(jobId)), owner);
        } catch (RuntimeException exception) {
            LOGGER.warn("Redis dispatch lease release failed for job {}", jobId);
        }
    }

    private static String key(UUID jobId) {
        return "analysis:dispatch:" + jobId;
    }
}
