package com.utility.ingestion.configuration;

import jakarta.validation.constraints.NotBlank;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.validation.annotation.Validated;

// A Java record: an immutable carrier of three values. @ConfigurationProperties binds the settings whose names begin
// with "security.jwt." to its components: issuer, jwkSetUri (the property "jwk-set-uri"), audience.
// @Validated + @NotBlank: a blank value stops the application at start-up with a message naming the property,
// instead of failing on the first request (test S17). The J2EE comparison is a missing JNDI resource, which
// stopped deployment instead of surfacing later.
@Validated
@ConfigurationProperties(prefix = "security.jwt")
public record SecurityProperties(
        @NotBlank String issuer,
        @NotBlank String jwkSetUri,
        @NotBlank String audience
) {
}
