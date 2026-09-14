package com.example.copilot.identity.api;

import java.util.Set;
import java.util.UUID;

public record TokenResponse(
        String accessToken, String tokenType, long expiresIn, UUID userId, UUID tenantId, Set<String> roles) {}
