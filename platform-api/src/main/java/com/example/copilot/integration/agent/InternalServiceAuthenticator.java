package com.example.copilot.integration.agent;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.stereotype.Component;

@Component
public class InternalServiceAuthenticator {

    private final byte[] expectedToken;

    public InternalServiceAuthenticator(AgentIntegrationProperties properties) {
        expectedToken = properties.serviceToken().getBytes(StandardCharsets.UTF_8);
    }

    public void verify(String authorization) {
        var supplied = authorization != null && authorization.startsWith("Bearer ")
                ? authorization.substring(7).getBytes(StandardCharsets.UTF_8)
                : new byte[0];
        if (!MessageDigest.isEqual(expectedToken, supplied)) {
            throw new AccessDeniedException("Invalid internal service credential.");
        }
    }
}
