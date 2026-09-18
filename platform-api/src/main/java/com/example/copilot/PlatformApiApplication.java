package com.example.copilot;

import com.example.copilot.bootstrap.DevelopmentBootstrapProperties;
import com.example.copilot.execution.AnalysisExecutionProperties;
import com.example.copilot.integration.agent.AgentIntegrationProperties;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.EnableConfigurationProperties;

@SpringBootApplication
@EnableConfigurationProperties({
    AgentIntegrationProperties.class,
    AnalysisExecutionProperties.class,
    DevelopmentBootstrapProperties.class
})
public class PlatformApiApplication {

    public static void main(String[] args) {
        SpringApplication.run(PlatformApiApplication.class, args);
    }
}
