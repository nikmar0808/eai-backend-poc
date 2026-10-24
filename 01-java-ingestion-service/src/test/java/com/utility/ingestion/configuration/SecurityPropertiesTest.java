package com.utility.ingestion.configuration;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.boot.test.context.runner.ApplicationContextRunner;

import static org.assertj.core.api.Assertions.assertThat;

class SecurityPropertiesTest {

    // A tiny configuration whose only job is to bind SecurityProperties, validation included.
    @EnableConfigurationProperties(SecurityProperties.class)
    static class Binding {
    }

    private static final String[] ALL_THREE = {
            "security.jwt.issuer=http://issuer.example/realms/x",
            "security.jwt.jwk-set-uri=http://keys.example/certs",
            "security.jwt.audience=my-api"
    };

    private final ApplicationContextRunner runner = new ApplicationContextRunner().withUserConfiguration(Binding.class);

    @Test
    void allThreeValuesBind() {                                                                // S16
        runner.withPropertyValues(ALL_THREE).run(context -> {
            assertThat(context).hasNotFailed();
            SecurityProperties properties = context.getBean(SecurityProperties.class);
            assertThat(properties.issuer()).isEqualTo("http://issuer.example/realms/x");
            assertThat(properties.jwkSetUri()).isEqualTo("http://keys.example/certs");   // "jwk-set-uri" -> jwkSetUri
            assertThat(properties.audience()).isEqualTo("my-api");
        });
    }

    // Later property values override earlier ones, so each run starts from a complete set and blanks one value.
    @ParameterizedTest(name = "a blank {0} stops start-up")
    @ValueSource(strings = {"issuer", "jwk-set-uri", "audience"})
    void aBlankValueStopsTheApplicationFromStarting(String name) {                             // S17 (3 executions)
        runner.withPropertyValues(ALL_THREE)
                .withPropertyValues("security.jwt." + name + "=")
                .run(context -> assertThat(context).hasFailed());
    }
}
