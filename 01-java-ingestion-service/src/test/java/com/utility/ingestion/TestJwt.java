package com.utility.ingestion;

import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.security.oauth2.jwt.JwtDecoder;

import java.time.Instant;

import static org.mockito.Mockito.when;

/** A fake caller for tests that need the gateway to accept a token without involving Keycloak. */
final class TestJwt {

    /** The text the test puts after "Bearer ". It is not a real JWT: the mocked decoder recognises it by equality. */
    static final String TOKEN_WITH_SCOPE = "test-token-with-ingest-scope";

    private TestJwt() {
    }

    /** A Jwt object the way the decoder would have produced it after a successful verification. */
    static Jwt withScope(String scope) {
        Instant now = Instant.now();
        return Jwt.withTokenValue("verified-by-the-mock")
                .header("alg", "none")                 // a Jwt must have at least one header and one claim
                .subject("test-client")
                .claim("scope", scope)                 // the claim Spring turns into SCOPE_ authorities
                .issuedAt(now)
                .expiresAt(now.plusSeconds(300))
                .build();
    }

    /** Call this in @BeforeEach: a @MockitoBean mock is reset after every test, so the stubbing is repeated. */
    static void acceptTheTestToken(JwtDecoder decoder) {
        when(decoder.decode(TOKEN_WITH_SCOPE)).thenReturn(withScope("ingest.write"));
    }
}
