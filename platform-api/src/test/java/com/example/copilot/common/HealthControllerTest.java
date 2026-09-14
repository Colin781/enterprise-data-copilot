package com.example.copilot.common;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;

class HealthControllerTest {

    private final HealthController controller = new HealthController();

    @Test
    void reportsPlatformServiceAsUp() {
        var response = controller.health();

        assertThat(response.service()).isEqualTo("platform-api");
        assertThat(response.status()).isEqualTo("UP");
        assertThat(response.timestamp()).isNotNull();
    }
}
