package com.utility.ingestion;

import com.github.tomakehurst.wiremock.junit5.WireMockExtension;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.RegisterExtension;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.boot.web.client.RestTemplateBuilder;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;

import java.time.Duration;

import static com.github.tomakehurst.wiremock.client.WireMock.okJson;
import static com.github.tomakehurst.wiremock.client.WireMock.post;
import static com.github.tomakehurst.wiremock.client.WireMock.urlEqualTo;
import static com.github.tomakehurst.wiremock.core.WireMockConfiguration.wireMockConfig;
import static org.assertj.core.api.Assertions.assertThat;
import static org.junit.jupiter.api.Assertions.assertTimeoutPreemptively;

@SpringBootTest(
        webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT,
        properties = "spring.http.client.read-timeout=1s")
class DownstreamTimeoutTest {

    @RegisterExtension
    static WireMockExtension python = WireMockExtension.newInstance()
            .options(wireMockConfig().dynamicPort())
            .build();

    @DynamicPropertySource
    static void pointTheGatewayAtTheStandIn(DynamicPropertyRegistry registry) {
        registry.add("integration.python.base-url", python::baseUrl);
        registry.add("integration.python.auth-token", () -> "timeout-test-token");
    }

    @LocalServerPort
    private int port;

    /**
     * The one-second property above applies to EVERY client Spring Boot configures in this context, including the
     * auto-configured TestRestTemplate. That client would give up at the same moment as the gateway. The test's own
     * client is therefore built by hand, with its own, longer timeout.
     */
    private TestRestTemplate patientClient() {
        return new TestRestTemplate(new RestTemplateBuilder()
                .rootUri("http://localhost:" + port)
                .readTimeout(Duration.ofSeconds(10)));
    }

    @Test
    void aDownstreamThatDoesNotAnswerFailsTheCallInsteadOfHangingTheGateway() {
        python.stubFor(post(urlEqualTo("/api/v1/transform"))
                .willReturn(okJson(TestData.PYTHON_RESPONSE_JSON).withFixedDelay(6000)));
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        TestRestTemplate rest = patientClient();

        // The gateway's own read timeout is one second, so it must answer well inside four seconds. If the
        // property were not honoured, it would wait the full six seconds and the preemptive timeout would fire first.
        ResponseEntity<String> response = assertTimeoutPreemptively(Duration.ofSeconds(4),
                () -> rest.postForEntity("/api/v1/ingest/bulk", new HttpEntity<>(TestData.VALID_JSON, headers), String.class));

        // Until Stage 6 maps it to 504 (see the contract), a timeout surfaces as the generic 500.
        assertThat(response.getStatusCode().is5xxServerError()).isTrue();
    }
}