package com.utility.ingestion.configuration;

import org.springframework.security.oauth2.core.DelegatingOAuth2TokenValidator;
import org.springframework.security.oauth2.core.OAuth2TokenValidator;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.security.oauth2.jwt.JwtClaimNames;
import org.springframework.security.oauth2.jwt.JwtClaimValidator;
import org.springframework.security.oauth2.jwt.JwtValidators;

import java.util.List;

/**
 * Builds the rules a token must satisfy, apart from its signature. A separate class with a plain static method,
 * so that the rules can be tested with a hand-built Jwt object: no key, no network, no Spring (tests S10 to S15).
 */
public final class JwtValidatorFactory {

    private JwtValidatorFactory() {
        // a utility class: no instances
    }

    public static OAuth2TokenValidator<Jwt> create(String issuer, String audience) {
        // Spring's ready-made pair: the token is not expired (exp, nbf, with 60 seconds of clock tolerance) and the
        // iss claim equals the issuer text exactly.
        OAuth2TokenValidator<Jwt> timeAndIssuer = JwtValidators.createDefaultWithIssuer(issuer);

        // Spring does NOT check the audience by default. This validator reads the aud claim, which the decoder has
        // already turned into a list of strings, and requires it to contain this API's name. A missing aud is null:
        // the null test makes that a rejection and not a NullPointerException (test S13).
        OAuth2TokenValidator<Jwt> audienceCheck = new JwtClaimValidator<List<String>>(
                JwtClaimNames.AUD, audiences -> audiences != null && audiences.contains(audience));

        // Runs both and collects every error. Both must pass.
        return new DelegatingOAuth2TokenValidator<>(timeAndIssuer, audienceCheck);
    }
}
