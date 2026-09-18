package com.example.copilot.bootstrap;

import com.example.copilot.datasource.domain.DataSource;
import com.example.copilot.datasource.repository.DataSourceRepository;
import com.example.copilot.identity.domain.AppUser;
import com.example.copilot.identity.domain.Tenant;
import com.example.copilot.identity.domain.UserRole;
import com.example.copilot.identity.repository.AppUserRepository;
import com.example.copilot.identity.repository.TenantRepository;
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
    private final PasswordEncoder passwordEncoder;

    public DevelopmentBootstrap(
            DevelopmentBootstrapProperties properties,
            TenantRepository tenants,
            AppUserRepository users,
            DataSourceRepository dataSources,
            PasswordEncoder passwordEncoder) {
        this.properties = properties;
        this.tenants = tenants;
        this.users = users;
        this.dataSources = dataSources;
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
        if (dataSources.findAllByTenantIdOrderByName(tenant.getId()).isEmpty()) {
            dataSources.save(new DataSource(
                    UUID.randomUUID(),
                    tenant.getId(),
                    "Northwind read-only",
                    "localhost",
                    5433,
                    "northwind",
                    "northwind",
                    "env:BUSINESS_DB_READONLY_PASSWORD"));
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
