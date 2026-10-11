package com.utility.ingestion.api;

import com.utility.ingestion.configuration.IntegrationProperties;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.http.client.ClientHttpRequestFactory;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientException;

@RestController
public class HealthController {

    private final RestClient downstreamClient;

    public HealthController(
            RestClient.Builder restClientBuilder,
            IntegrationProperties properties,
            @Qualifier("downstreamProbeRequestFactory") ClientHttpRequestFactory probeRequestFactory) {
        this.downstreamClient = restClientBuilder
                .baseUrl(properties.baseUrl())
                .requestFactory(probeRequestFactory)
                .build();
    }

    public enum ServiceStatus { UP, DOWN }

    public record HealthStatus(ServiceStatus status, ServiceStatus pythonValidator) {}

    /**
     * The gateway has one dependency, the Python service, whose own /health checks the database. The gateway is
     * therefore ready exactly when that probe succeeds, and the overall status equals the downstream status.
     */
    @GetMapping("/health")
    public ResponseEntity<HealthStatus> health() {
        ServiceStatus downstream = probeDownstream();
        HealthStatus body = new HealthStatus(downstream, downstream);
        return downstream == ServiceStatus.UP
                ? ResponseEntity.ok(body)
                : ResponseEntity.status(HttpStatus.SERVICE_UNAVAILABLE).body(body);
    }

    private ServiceStatus probeDownstream() {
        try {
            downstreamClient.get().uri("/health").retrieve().toBodilessEntity();
            return ServiceStatus.UP;
        } catch (RestClientException e) {
            // Python answers 503 when its database is down; that arrives here as an exception too.
            return ServiceStatus.DOWN;
        }
    }
}
