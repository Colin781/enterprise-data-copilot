package com.example.copilot.identity.api;

import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

public record LoginRequest(
        @NotBlank @Size(max = 80) String tenantSlug,
        @NotBlank @Email @Size(max = 254) String email,
        @NotBlank @Size(max = 200) String password) {}
