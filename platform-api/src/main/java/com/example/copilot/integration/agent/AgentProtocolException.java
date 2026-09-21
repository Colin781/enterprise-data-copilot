package com.example.copilot.integration.agent;

public final class AgentProtocolException extends RuntimeException {

    public static final String CODE = "AGENT_INVALID_RESPONSE";

    public AgentProtocolException() {
        super("Agent Service returned an invalid response.");
    }

    public AgentProtocolException(Throwable cause) {
        super("Agent Service returned an invalid response.", cause);
    }
}
