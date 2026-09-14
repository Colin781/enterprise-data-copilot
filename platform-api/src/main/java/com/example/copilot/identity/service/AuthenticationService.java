package com.example.copilot.identity.service;

import com.example.copilot.identity.api.LoginRequest;
import com.example.copilot.identity.api.TokenResponse;
import com.example.copilot.identity.domain.AppUser;
import com.example.copilot.identity.repository.AppUserRepository;
import com.example.copilot.identity.repository.TenantRepository;
import com.example.copilot.security.SecurityProperties;
import java.time.Instant;
import java.util.stream.Collectors;
import org.springframework.security.authentication.BadCredentialsException;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.security.oauth2.jose.jws.MacAlgorithm;
import org.springframework.security.oauth2.jwt.JwsHeader;
import org.springframework.security.oauth2.jwt.JwtClaimsSet;
import org.springframework.security.oauth2.jwt.JwtEncoder;
import org.springframework.security.oauth2.jwt.JwtEncoderParameters;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class AuthenticationService {

    private final TenantRepository tenantRepository;
    private final AppUserRepository userRepository;
    private final PasswordEncoder passwordEncoder;
    private final JwtEncoder jwtEncoder;
    private final SecurityProperties securityProperties;

    public AuthenticationService(
            TenantRepository tenantRepository,
            AppUserRepository userRepository,
            PasswordEncoder passwordEncoder,
            JwtEncoder jwtEncoder,
            SecurityProperties securityProperties) {
        this.tenantRepository = tenantRepository;
        this.userRepository = userRepository;
        this.passwordEncoder = passwordEncoder;
        this.jwtEncoder = jwtEncoder;
        this.securityProperties = securityProperties;
    }

    @Transactional(readOnly = true)
    public TokenResponse login(LoginRequest request) {
        var tenant = tenantRepository
                .findBySlugAndEnabledTrue(request.tenantSlug())
                .orElseThrow(AuthenticationService::invalidCredentials);
        var user = userRepository
                .findByTenantIdAndEmailIgnoreCase(tenant.getId(), request.email())
                .filter(AppUser::isEnabled)
                .orElseThrow(AuthenticationService::invalidCredentials);
        if (!passwordEncoder.matches(request.password(), user.getPasswordHash())) {
            throw invalidCredentials();
        }

        var now = Instant.now();
        var expiresAt = now.plus(securityProperties.accessTokenTtl());
        var roles = user.getRoles().stream().map(Enum::name).collect(Collectors.toUnmodifiableSet());
        var claims = JwtClaimsSet.builder()
                .issuer(securityProperties.jwtIssuer())
                .issuedAt(now)
                .expiresAt(expiresAt)
                .subject(user.getId().toString())
                .claim("tenant_id", tenant.getId().toString())
                .claim("roles", roles)
                .build();
        var header = JwsHeader.with(MacAlgorithm.HS256).build();
        var token = jwtEncoder.encode(JwtEncoderParameters.from(header, claims)).getTokenValue();

        return new TokenResponse(
                token, "Bearer", securityProperties.accessTokenTtl().toSeconds(), user.getId(), tenant.getId(), roles);
    }

    private static BadCredentialsException invalidCredentials() {
        return new BadCredentialsException("Invalid credentials");
    }
}
