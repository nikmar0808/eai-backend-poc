package com.utility.ingestion;

import com.github.tomakehurst.wiremock.http.Fault;
import com.github.tomakehurst.wiremock.junit5.WireMockExtension;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.RegisterExtension;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;

import org.springframework.security.oauth2.jwt.JwtDecoder;
import org.springframework.test.context.bean.override.mockito.MockitoBean;

import java.time.Duration;

import static com.github.tomakehurst.wiremock.client.WireMock.aResponse;
import static com.github.tomakehurst.wiremock.client.WireMock.anyUrl;
import static com.github.tomakehurst.wiremock.client.WireMock.equalTo;
import static com.github.tomakehurst.wiremock.client.WireMock.get;
import static com.github.tomakehurst.wiremock.client.WireMock.matchingJsonPath;
import static com.github.tomakehurst.wiremock.client.WireMock.okJson;
import static com.github.tomakehurst.wiremock.client.WireMock.post;
import static com.github.tomakehurst.wiremock.client.WireMock.postRequestedFor;
import static com.github.tomakehurst.wiremock.client.WireMock.urlEqualTo;
import static com.github.tomakehurst.wiremock.core.WireMockConfiguration.wireMockConfig;
import static org.assertj.core.api.Assertions.assertThat;
import static org.junit.jupiter.api.Assertions.assertTimeoutPreemptively;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class IngestionWiringTest {

    private static final String TOKEN = "wiring-test-token";

    @RegisterExtension
    static WireMockExtension python = WireMockExtension.newInstance()
            .options(wireMockConfig().dynamicPort())
            .build();

    @DynamicPropertySource
    static void pointTheGatewayAtTheStandIn(DynamicPropertyRegistry registry) {
        registry.add("integration.python.base-url", python::baseUrl);
        registry.add("integration.python.auth-token", () -> TOKEN);
    }

    @Autowired
    private TestRestTemplate rest;

    @MockitoBean                     // replaces the real decoder (which would call Keycloak) with a mock
    private JwtDecoder jwtDecoder;

    @BeforeEach
    void resetStubs() {
        python.resetAll();
        TestJwt.acceptTheTestToken(jwtDecoder);     // a @MockitoBean is reset after each test, so stub it before each one
    }

    private static HttpEntity<String> json(String body) {
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        headers.setBearerAuth(TestJwt.TOKEN_WITH_SCOPE);     // Authorization: Bearer test-token-with-ingest-scope
        return new HttpEntity<>(body, headers);
    }

    private void pythonAnswersTransformWithTheValidResponse() {
        python.stubFor(post(urlEqualTo("/api/v1/transform"))
                .withHeader("X-EAI-TOKEN", equalTo(TOKEN))
                .willReturn(okJson(TestData.PYTHON_RESPONSE_JSON)));
    }

    @Test
    void forwardsAValidRequestWithTheTokenAndIsoTimestampsAndReturnsJson() {
        pythonAnswersTransformWithTheValidResponse();

        ResponseEntity<String> response = rest.postForEntity("/api/v1/ingest/bulk", json(TestData.VALID_JSON), String.class);

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(response.getHeaders().getContentType().isCompatibleWith(MediaType.APPLICATION_JSON)).isTrue();
        assertThat(response.getBody()).contains("\"intervals_saved\":1");
        // The wire format is asserted here, where Spring Boot's own JSON configuration is in force:
        // the timestamp must travel as an ISO string, never as a number.
        // Finding D23 guard: the JDK's default HTTP client would add an "Upgrade: h2c" offer to this request,
        // which python-validator's server rejects with 400. The HTTP/1.1 client sends none.
        python.verify(postRequestedFor(urlEqualTo("/api/v1/transform"))
                .withoutHeader("Upgrade")
                .withRequestBody(matchingJsonPath("$.meter_id", equalTo("MTR-POC2-001")))
                .withRequestBody(matchingJsonPath("$.readings[0].timestamp", equalTo("2026-10-09T00:00:00Z"))));
    }

    @Test
    void characterisation_anOffsetIsNormalisedToUtcBeforeForwarding() {
        // 05:30 at +05:30 is the same instant as 00:00Z. Jackson, as Spring Boot configures it, adjusts offset
        // date-times to UTC. If the observed value differs, the learner records the observed behaviour here and
        // says why in the pull request: this is a characterisation, not a requirement.
        pythonAnswersTransformWithTheValidResponse();
        String withOffset = TestData.VALID_JSON.replace("2026-10-09T00:00:00Z", "2026-10-09T05:30:00+05:30");

        ResponseEntity<String> response = rest.postForEntity("/api/v1/ingest/bulk", json(withOffset), String.class);

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.OK);
        python.verify(postRequestedFor(urlEqualTo("/api/v1/transform"))
                .withRequestBody(matchingJsonPath("$.readings[0].timestamp", equalTo("2026-10-09T00:00:00Z"))));
    }

    @Test
    void aRequestRejectedByTheGatewayNeverReachesPython() {
        String invalid = TestData.VALID_JSON.replace("\"voltage\":230.0", "\"voltage\":50.0");

        ResponseEntity<String> response = rest.postForEntity("/api/v1/ingest/bulk", json(invalid), String.class);

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.BAD_REQUEST);
        python.verify(0, postRequestedFor(anyUrl()));
    }

    @Test
    void documentsD3_aRejectionByPythonBecomesAGeneric500() {
        // Finding D3 (downstream half). The contract says 502; Stage 6 implements it and flips this assertion.
        python.stubFor(post(urlEqualTo("/api/v1/transform"))
                .willReturn(aResponse().withStatus(422).withHeader("Content-Type", "application/json")
                        .withBody("{\"detail\":[]}")));

        ResponseEntity<String> response = rest.postForEntity("/api/v1/ingest/bulk", json(TestData.VALID_JSON), String.class);

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.INTERNAL_SERVER_ERROR);
    }

    @Test
    void documentsD3_aBrokenConnectionToPythonBecomesAGeneric500() {
        python.stubFor(post(urlEqualTo("/api/v1/transform"))
                .willReturn(aResponse().withFault(Fault.CONNECTION_RESET_BY_PEER)));

        ResponseEntity<String> response = rest.postForEntity("/api/v1/ingest/bulk", json(TestData.VALID_JSON), String.class);

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.INTERNAL_SERVER_ERROR);
    }

    @Test
    void aSlowAnswerIsNotCutOffByTheProbeTimeout() {
        // Guards against the probe's two-second request factory leaking into the main call: this answer takes
        // three seconds and must still succeed.
        python.stubFor(post(urlEqualTo("/api/v1/transform"))
                .willReturn(okJson(TestData.PYTHON_RESPONSE_JSON).withFixedDelay(3000)));

        ResponseEntity<String> response = assertTimeoutPreemptively(Duration.ofSeconds(8),
                () -> rest.postForEntity("/api/v1/ingest/bulk", json(TestData.VALID_JSON), String.class));

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.OK);
    }

    @Test
    void healthReflectsPythonsHealth() {
        python.stubFor(get(urlEqualTo("/health")).willReturn(aResponse().withStatus(200)));
        assertThat(rest.getForEntity("/health", String.class).getBody()).contains("\"status\":\"UP\"");

        python.stubFor(get(urlEqualTo("/health")).willReturn(aResponse().withStatus(503)));
        ResponseEntity<String> down = rest.getForEntity("/health", String.class);
        assertThat(down.getStatusCode()).isEqualTo(HttpStatus.SERVICE_UNAVAILABLE);
        assertThat(down.getBody()).contains("\"status\":\"DOWN\"");
    }

    @Test
    void theGeneratedApiDocumentIsNotExposedByDefault() {
        assertThat(rest.getForEntity("/v3/api-docs", String.class).getStatusCode()).isEqualTo(HttpStatus.NOT_FOUND);
    }
}
