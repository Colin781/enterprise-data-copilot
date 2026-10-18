package com.example.copilot;

import com.example.copilot.config.properties.AgentIntegrationProperties;
import com.example.copilot.config.properties.AnalysisExecutionProperties;
import com.example.copilot.config.properties.DataSourceRegistrationProperties;
import com.example.copilot.config.properties.DevelopmentBootstrapProperties;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.EnableConfigurationProperties;

@SpringBootApplication
@EnableConfigurationProperties({
    AgentIntegrationProperties.class,
    AnalysisExecutionProperties.class,
    DevelopmentBootstrapProperties.class,
    DataSourceRegistrationProperties.class
})
public class PlatformApiApplication {

    public static void main(String[] args) {
        SpringApplication.run(PlatformApiApplication.class, args);
    }
}
