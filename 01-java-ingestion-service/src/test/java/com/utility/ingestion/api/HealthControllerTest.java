package com.utility.ingestion.api;

import com.github.tomakehurst.wiremock.junit5.WireMockExtension;
import com.utility.ingestion.api.HealthController.HealthStatus;
import com.utility.ingestion.api.HealthController.ServiceStatus;
import com.utility.ingestion.configuration.HttpClientConfiguration;
import com.utility.ingestion.configuration.IntegrationProperties;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.RegisterExtension;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.client.RestClient;

import java.time.Duration;

import static com.github.tomakehurst.wiremock.client.WireMock.aResponse;
import static com.github.tomakehurst.wiremock.client.WireMock.get;
import static com.github.tomakehurst.wiremock.client.WireMock.getRequestedFor;
import static com.github.tomakehurst.wiremock.client.WireMock.urlEqualTo;
import static com.github.tomakehurst.wiremock.core.WireMockConfiguration.wireMockConfig;
import static org.assertj.core.api.Assertions.assertThat;
import static org.junit.jupiter.api.Assertions.assertTimeoutPreemptively;

class HealthControllerTest {

    @RegisterExtension
    static WireMockExtension python = WireMockExtension.newInstance()
            .options(wireMockConfig().dynamicPort())
            .build();

    @BeforeEach
    void resetStubs() {
        python.resetAll();
    }

    /** Built by hand, with the real probe request factory, so the real timeouts apply. */
    private static HealthController controllerFor(String baseUrl) {
        return new HealthController(
                RestClient.builder(),
                new IntegrationProperties(baseUrl, "test-token"),
                new HttpClientConfiguration().downstreamProbeRequestFactory());
    }

    @Test
    void reportsUpWhenPythonReportsUp() {
        python.stubFor(get(urlEqualTo("/health")).willReturn(aResponse().withStatus(200)));

        ResponseEntity<HealthStatus> response = controllerFor(python.baseUrl()).health();

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(response.getBody()).isEqualTo(new HealthStatus(ServiceStatus.UP, ServiceStatus.UP));
    }

    @Test
    void reportsDownWith503WhenPythonReportsItsDatabaseDown() {
        python.stubFor(get(urlEqualTo("/health")).willReturn(aResponse().withStatus(503)));

        ResponseEntity<HealthStatus> response = controllerFor(python.baseUrl()).health();

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.SERVICE_UNAVAILABLE);
        assertThat(response.getBody()).isEqualTo(new HealthStatus(ServiceStatus.DOWN, ServiceStatus.DOWN));
    }

    @Test
    void probesPythonsHealthRouteAndNotItsRoot() {
        // Finding D18: the root route checks nothing downstream; /health checks the database.
        python.stubFor(get(urlEqualTo("/health")).willReturn(aResponse().withStatus(200)));

        controllerFor(python.baseUrl()).health();

        python.verify(1, getRequestedFor(urlEqualTo("/health")));
        python.verify(0, getRequestedFor(urlEqualTo("/")));
    }

    @Test
    void reportsDownWhenTheConnectionIsRefused() {
        ResponseEntity<HealthStatus> response = controllerFor("http://localhost:1").health();

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.SERVICE_UNAVAILABLE);
        assertThat(response.getBody().status()).isEqualTo(ServiceStatus.DOWN);
    }

    @Test
    void reportsDownQuicklyWhenPythonHangs() {
        // The probe has a two-second read timeout, so a hung downstream fails /health in about two seconds.
        python.stubFor(get(urlEqualTo("/health")).willReturn(aResponse().withStatus(200).withFixedDelay(5000)));

        ResponseEntity<HealthStatus> response = assertTimeoutPreemptively(
                Duration.ofMillis(3500), () -> controllerFor(python.baseUrl()).health());

        assertThat(response.getBody().status()).isEqualTo(ServiceStatus.DOWN);
    }
}
