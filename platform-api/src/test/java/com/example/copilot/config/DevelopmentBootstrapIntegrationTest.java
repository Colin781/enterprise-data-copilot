package com.example.copilot.config;

import static org.assertj.core.api.Assertions.assertThat;

import com.example.copilot.config.properties.DataSourceRegistrationProperties;
import com.example.copilot.config.properties.DevelopmentBootstrapProperties;
import com.example.copilot.entity.DataSource;
import com.example.copilot.repository.AppUserRepository;
import com.example.copilot.repository.DataSourceRepository;
import com.example.copilot.repository.TenantRepository;
import com.example.copilot.support.PostgresIntegrationTest;
import java.util.Set;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.DefaultApplicationArguments;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.transaction.annotation.Transactional;

@SpringBootTest
@Transactional
class DevelopmentBootstrapIntegrationTest extends PostgresIntegrationTest {

    @Autowired
    TenantRepository tenants;

    @Autowired
    AppUserRepository users;

    @Autowired
    DataSourceRepository dataSources;

    @Autowired
    PasswordEncoder passwordEncoder;

    @Test
    void freshBootstrapCreatesOneSourceAndRepeatedStartupReusesIt() {
        var slug = "bootstrap-" + UUID.randomUUID();
        runBootstrap(slug, "localhost", 5433);
        var tenant = tenants.findBySlugAndEnabledTrue(slug).orElseThrow();
        var first = dataSources.findAllByTenantIdOrderByName(tenant.getId());
        assertThat(first).hasSize(1);
        assertThat(first.getFirst().getName()).isEqualTo("Northwind read-only");

        runBootstrap(slug, "localhost", 5433);
        assertThat(dataSources.findAllByTenantIdOrderByName(tenant.getId()))
                .extracting(DataSource::getId)
                .containsExactly(first.getFirst().getId());
    }

    @Test
    void switchingToComposePreservesOldSourcesAndAvoidsAllOccupiedNames() {
        var slug = "bootstrap-" + UUID.randomUUID();
        runBootstrap(slug, "localhost", 5433);
        var tenant = tenants.findBySlugAndEnabledTrue(slug).orElseThrow();
        var original = dataSources.findAllByTenantIdOrderByName(tenant.getId()).getFirst();
        dataSources.saveAndFlush(new DataSource(
                UUID.randomUUID(),
                tenant.getId(),
                "Northwind read-only (2)",
                "localhost",
                5434,
                "northwind",
                "northwind",
                "env:BUSINESS_DB_READONLY_PASSWORD"));

        runBootstrap(slug, "business-db", 5432);
        var sources = dataSources.findAllByTenantIdOrderByName(tenant.getId());
        assertThat(sources).hasSize(3);
        assertThat(sources)
                .extracting(DataSource::getName)
                .containsExactly("Northwind read-only", "Northwind read-only (2)", "Northwind read-only (3)");
        var current = sources.stream()
                .filter(source -> source.getHost().equals("business-db"))
                .findFirst()
                .orElseThrow();
        assertThat(current.getPort()).isEqualTo(5432);
        assertThat(dataSources.findById(original.getId()).orElseThrow().getHost())
                .isEqualTo("localhost");
        assertThat(original.getName()).isEqualTo("Northwind read-only");

        runBootstrap(slug, "business-db", 5432);
        runBootstrap(slug, "localhost", 5433);
        assertThat(dataSources.findAllByTenantIdOrderByName(tenant.getId()))
                .extracting(DataSource::getId)
                .containsExactlyElementsOf(
                        sources.stream().map(DataSource::getId).toList());
    }

    private void runBootstrap(String slug, String host, int port) {
        var properties = new DevelopmentBootstrapProperties(
                true, slug, "Bootstrap test", "admin@test.local", "analyst@test.local", "test-password");
        var registration = new DataSourceRegistrationProperties(
                Set.of("localhost", "business-db"),
                host,
                port,
                "northwind",
                "northwind",
                "env:BUSINESS_DB_READONLY_PASSWORD");
        new DevelopmentBootstrap(properties, tenants, users, dataSources, registration, passwordEncoder)
                .run(new DefaultApplicationArguments());
        dataSources.flush();
    }
}
