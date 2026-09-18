package com.example.copilot.bootstrap;

import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.boot.context.properties.bind.DefaultValue;

@ConfigurationProperties("platform.bootstrap")
public record DevelopmentBootstrapProperties(
        @DefaultValue("false") boolean enabled,
        @DefaultValue("northwind") String tenantSlug,
        @DefaultValue("Northwind Demo") String tenantName,
        @DefaultValue("admin@northwind.local") String adminEmail,
        @DefaultValue("analyst@northwind.local") String analystEmail,
        @DefaultValue("change-me-demo") String password) {}
