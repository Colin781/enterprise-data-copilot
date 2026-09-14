package com.example.copilot.security;

import java.util.Set;
import java.util.UUID;
import org.springframework.security.oauth2.server.resource.authentication.JwtAuthenticationToken;
import org.springframework.stereotype.Component;

@Component
public class CallerIdentity {

    public Caller current(JwtAuthenticationToken authentication) {
        var jwt = authentication.getToken();
        var userId = UUID.fromString(jwt.getSubject());
        var tenantId = UUID.fromString(jwt.getClaimAsString("tenant_id"));
        var roles = Set.copyOf(jwt.getClaimAsStringList("roles"));
        return new Caller(userId, tenantId, roles);
    }

    public record Caller(UUID userId, UUID tenantId, Set<String> roles) {}
}
