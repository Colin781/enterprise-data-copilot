package com.example.copilot.config;

import com.example.copilot.config.properties.DataSourceRegistrationProperties;
import com.example.copilot.config.properties.DevelopmentBootstrapProperties;
import com.example.copilot.entity.AppUser;
import com.example.copilot.entity.DataSource;
import com.example.copilot.entity.Tenant;
import com.example.copilot.enums.UserRole;
import com.example.copilot.repository.AppUserRepository;
import com.example.copilot.repository.DataSourceRepository;
import com.example.copilot.repository.TenantRepository;
import java.util.HashSet;
import java.util.Set;
import java.util.UUID;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

@Component
public class DevelopmentBootstrap implements ApplicationRunner {

    private static final Logger LOGGER = LoggerFactory.getLogger(DevelopmentBootstrap.class);

    private final DevelopmentBootstrapProperties properties;
    private final TenantRepository tenants;
    private final AppUserRepository users;
    private final DataSourceRepository dataSources;
    private final DataSourceRegistrationProperties registrationProperties;
    private final PasswordEncoder passwordEncoder;

    public DevelopmentBootstrap(
            DevelopmentBootstrapProperties properties,
            TenantRepository tenants,
            AppUserRepository users,
            DataSourceRepository dataSources,
            DataSourceRegistrationProperties registrationProperties,
            PasswordEncoder passwordEncoder) {
        this.properties = properties;
        this.tenants = tenants;
        this.users = users;
        this.dataSources = dataSources;
        this.registrationProperties = registrationProperties;
        this.passwordEncoder = passwordEncoder;
    }

    @Override
    @Transactional
    public void run(ApplicationArguments arguments) {
        if (!properties.enabled()) {
            return;
        }
        var tenant = tenants.findBySlugAndEnabledTrue(properties.tenantSlug())
                .orElseGet(() ->
                        tenants.save(new Tenant(UUID.randomUUID(), properties.tenantSlug(), properties.tenantName())));
        ensureUser(tenant, properties.adminEmail(), "Demo Admin", Set.of(UserRole.ADMIN));
        ensureUser(tenant, properties.analystEmail(), "Demo Analyst", Set.of(UserRole.ANALYST));
        var existingSources = dataSources.findAllByTenantIdOrderByName(tenant.getId());
        if (existingSources.stream().noneMatch(registrationProperties::matches)) {
            var existingNames = new HashSet<String>();
            existingSources.forEach(source -> existingNames.add(source.getName()));
            var name = "Northwind read-only";
            // Switching between host and Compose connections must preserve old registrations.
            for (int suffix = 2; existingNames.contains(name); suffix++) {
                name = "Northwind read-only (" + suffix + ")";
            }
            dataSources.save(new DataSource(
                    UUID.randomUUID(),
                    tenant.getId(),
                    name,
                    registrationProperties.demoHost(),
                    registrationProperties.demoPort(),
                    registrationProperties.demoDatabaseName(),
                    registrationProperties.demoAllowedSchema(),
                    registrationProperties.demoSecretRef()));
        }
        LOGGER.warn(
                "Local demo bootstrap is enabled for tenant '{}'; disable PLATFORM_BOOTSTRAP_ENABLED outside development",
                properties.tenantSlug());
    }

    private void ensureUser(Tenant tenant, String email, String displayName, Set<UserRole> roles) {
        if (users.findByTenantIdAndEmailIgnoreCase(tenant.getId(), email).isEmpty()) {
            users.save(new AppUser(
                    UUID.randomUUID(),
                    tenant.getId(),
                    email,
                    passwordEncoder.encode(properties.password()),
                    displayName,
                    roles));
        }
    }
}
