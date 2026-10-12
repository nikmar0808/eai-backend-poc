package com.utility.ingestion;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.core.env.Environment;

import java.time.Duration;

import static org.assertj.core.api.Assertions.assertThat;

@SpringBootTest(properties = "integration.python.auth-token=settings-test-token")
class HttpClientSettingsTest {

    @Autowired
    private Environment environment;

    @Test
    void theGatewayUsesTheHttp11Client() {
        // Finding D23: with the JDK's default client every forwarded request offers an HTTP/2 upgrade that
        // python-validator's server rejects with 400.
        assertThat(environment.getProperty("spring.http.client.factory")).isEqualTo("simple");
    }

    @Test
    void theConnectTimeoutIsConfiguredAndShort() {
        assertThat(environment.getProperty("spring.http.client.connect-timeout", Duration.class))
                .isNotNull()
                .isLessThanOrEqualTo(Duration.ofSeconds(10));
    }

    @Test
    void theReadTimeoutIsConfiguredAndBounded() {
        assertThat(environment.getProperty("spring.http.client.read-timeout", Duration.class))
                .isNotNull()
                .isLessThanOrEqualTo(Duration.ofSeconds(60));
    }
}
