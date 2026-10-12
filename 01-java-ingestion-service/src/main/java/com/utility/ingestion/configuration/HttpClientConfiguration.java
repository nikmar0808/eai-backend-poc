package com.utility.ingestion.configuration;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.client.ClientHttpRequestFactory;
import org.springframework.http.client.SimpleClientHttpRequestFactory;

import java.time.Duration;

@Configuration
public class HttpClientConfiguration {

    private static final Duration PROBE_TIMEOUT = Duration.ofSeconds(2);

    /** Request factory for the health probe only: short timeouts, so a hung downstream fails /health quickly. */
    @Bean
    public ClientHttpRequestFactory downstreamProbeRequestFactory() {
        SimpleClientHttpRequestFactory factory = new SimpleClientHttpRequestFactory();
        factory.setConnectTimeout((int) PROBE_TIMEOUT.toMillis());
        factory.setReadTimeout((int) PROBE_TIMEOUT.toMillis());
        return factory;
    }
    /** Customizer for configuring downstream timeouts if Spring Boot does not apply `spring.http.client.read-timeout` to the client*/
    // @Bean
    // public org.springframework.boot.web.client.RestClientCustomizer downstreamTimeouts(
    //         @org.springframework.beans.factory.annotation.Value("${spring.http.client.read-timeout:30s}") Duration readTimeout,
    //         @org.springframework.beans.factory.annotation.Value("${spring.http.client.connect-timeout:5s}") Duration connectTimeout) {
    //     return builder -> {
    //         SimpleClientHttpRequestFactory factory = new SimpleClientHttpRequestFactory();
    //         factory.setConnectTimeout((int) connectTimeout.toMillis());
    //         factory.setReadTimeout((int) readTimeout.toMillis());
    //         builder.requestFactory(factory);
    //     };
    // }    
}
