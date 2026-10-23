package com.utility.ingestion;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.ResponseEntity;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.boot.test.context.SpringBootTest.WebEnvironment.RANDOM_PORT;

// The token property is needed by the start-up check of IntegrationProperties (Stage 2, T17); the Python address is
// left at its default, where nothing listens, so /health answers 503 here.
@SpringBootTest(webEnvironment = RANDOM_PORT, properties = "integration.python.auth-token=test-token")
class SecurityWiringTest {

    private static final String PROTECTED = "/api/v1/ingest/bulk";

    @Autowired
    private TestRestTemplate rest;

    @Test
    void noTokenOnAProtectedPathGives401() {                                                   // S18
        // GET, not POST: the answer is decided by security before routing, so the method does not matter, and a GET
        // avoids a quirk of the JDK HTTP client when a POST is answered 401.
        ResponseEntity<String> response = rest.getForEntity(PROTECTED, String.class);

        assertThat(response.getStatusCode().value()).isEqualTo(401);
        assertThat(response.getBody()).contains("\"status\":401");
    }

    @Test
    void aGarbageBearerTokenGives401WithABearerChallenge() {                                   // S19
        HttpHeaders headers = new HttpHeaders();
        headers.setBearerAuth("this-is-not-a-jwt");

        ResponseEntity<String> response =
                rest.exchange(PROTECTED, HttpMethod.GET, new HttpEntity<>(headers), String.class);

        assertThat(response.getStatusCode().value()).isEqualTo(401);
        // RFC 6750: a token was presented and was bad, so the challenge says error="invalid_token".
        assertThat(response.getHeaders().getFirst("WWW-Authenticate")).startsWith("Bearer").contains("invalid_token");
    }

    @Test
    void healthIsReachableWithoutAToken() {                                                    // S20
        ResponseEntity<String> response = rest.getForEntity("/health", String.class);

        // Python is not running here, so the probe fails and /health says 503 DOWN. What matters is that it is not
        // 401: the security filter let an anonymous request reach the controller.
        assertThat(response.getStatusCode().value()).isIn(200, 503);
    }
}
