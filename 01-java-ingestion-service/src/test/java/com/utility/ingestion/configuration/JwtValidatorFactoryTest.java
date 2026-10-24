package com.utility.ingestion.configuration;

import org.junit.jupiter.api.Test;
import org.springframework.security.oauth2.core.OAuth2TokenValidator;
import org.springframework.security.oauth2.core.OAuth2TokenValidatorResult;
import org.springframework.security.oauth2.jwt.Jwt;

import java.time.Instant;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

class JwtValidatorFactoryTest {

    private static final String ISSUER = "http://localhost:8180/realms/eai";
    private static final String AUDIENCE = "eai-gateway";

    private final OAuth2TokenValidator<Jwt> validator = JwtValidatorFactory.create(ISSUER, AUDIENCE);

    /** A token that satisfies every rule. Each test changes ONE thing, so a failure names its cause. */
    private static Jwt.Builder goodToken() {
        Instant now = Instant.now();
        return Jwt.withTokenValue("not-a-real-token")
                .header("alg", "RS256")
                .issuer(ISSUER)
                .audience(List.of(AUDIENCE))
                .subject("ingest-client")
                .issuedAt(now.minusSeconds(10))
                .expiresAt(now.plusSeconds(290));
    }

    @Test
    void acceptsATokenWithTheRightIssuerAudienceAndExpiry() {                                 // S10
        assertThat(validator.validate(goodToken().build()).hasErrors()).isFalse();
    }

    @Test
    void rejectsAWrongIssuer() {                                                               // S11
        // The container address instead of the published name: the trap of A4, as a unit test.
        Jwt token = goodToken().issuer("http://keycloak:8080/realms/eai").build();

        OAuth2TokenValidatorResult result = validator.validate(token);

        assertThat(result.hasErrors()).isTrue();
        assertThat(result.getErrors()).as("only the issuer rule fired").hasSize(1);
    }

    @Test
    void rejectsAWrongAudience() {                                                             // S12
        Jwt token = goodToken().audience(List.of("some-other-api")).build();

        OAuth2TokenValidatorResult result = validator.validate(token);

        assertThat(result.hasErrors()).isTrue();
        assertThat(result.getErrors()).as("only the audience rule fired").hasSize(1);
    }

    @Test
    void rejectsATokenWithoutAudience() {                                                      // S13
        // Built from scratch because the builder cannot remove an audience once it has been set.
        Instant now = Instant.now();
        Jwt token = Jwt.withTokenValue("not-a-real-token")
                .header("alg", "RS256")
                .issuer(ISSUER)
                .subject("outsider-client")
                .issuedAt(now.minusSeconds(10))
                .expiresAt(now.plusSeconds(290))
                .build();

        assertThat(validator.validate(token).hasErrors()).isTrue();      // a rejection, not a NullPointerException
    }

    @Test
    void rejectsAnExpiredToken() {                                                             // S14
        // 100 seconds past: beyond the 60 seconds of clock tolerance that Spring allows by default.
        Instant now = Instant.now();
        Jwt token = goodToken().issuedAt(now.minusSeconds(400)).expiresAt(now.minusSeconds(100)).build();

        OAuth2TokenValidatorResult result = validator.validate(token);

        assertThat(result.hasErrors()).isTrue();
        assertThat(result.getErrors()).as("only the expiry rule fired").hasSize(1);
    }

    @Test
    void acceptsAnAudienceListContainingTheExpectedName() {                                    // S15
        // A token may be meant for several APIs. Containment, not equality, is the rule.
        Jwt token = goodToken().audience(List.of("account", AUDIENCE)).build();

        assertThat(validator.validate(token).hasErrors()).isFalse();
    }
}
