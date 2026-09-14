package com.example.copilot.common.api;

public class IdempotencyConflictException extends RuntimeException {
    public IdempotencyConflictException() {
        super("The idempotency key was already used for a different request.");
    }
}
