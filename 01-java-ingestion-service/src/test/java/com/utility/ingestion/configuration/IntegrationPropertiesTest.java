package com.utility.ingestion.configuration;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;
import org.springframework.boot.test.context.runner.ApplicationContextRunner;   // a mini application context for tests
import org.springframework.boot.context.properties.EnableConfigurationProperties;

import static org.assertj.core.api.Assertions.assertThat;

class IntegrationPropertiesTest {

    // Binds ONLY IntegrationProperties. AppConfiguration also registers SecurityProperties (Stage 5), whose required
    // settings are not present in this miniature context; using it would make every start-up fail, and the tests
    // that expect a failure would pass for the wrong reason.
    @EnableConfigurationProperties(IntegrationProperties.class)
    static class Binding {
    }
    
    // withUserConfiguration: the ONLY configuration class in the mini context. Binding carries
    // @EnableConfigurationProperties(IntegrationProperties.class), which is what binds and validates the record.
    // The runner is immutable: each withPropertyValues(...) returns a new, adjusted runner.
    private final ApplicationContextRunner runner = new ApplicationContextRunner()
            .withUserConfiguration(Binding.class);

    @Test
    void bothSettingsBindFromTheirPropertyNames() {                               // T16
        runner.withPropertyValues(
                        "integration.python.base-url=http://python.test:8082",
                        "integration.python.auth-token=secret-token")
                .run(context -> {                                                  // the lambda receives the started context
                    assertThat(context).hasNotFailed();
                    IntegrationProperties properties = context.getBean(IntegrationProperties.class);
                    assertThat(properties.baseUrl()).isEqualTo("http://python.test:8082");
                    assertThat(properties.authToken()).isEqualTo("secret-token");
                });
    }

    // Column 1: the property that is left blank. Column 2: the record field the error message must name.
    @ParameterizedTest(name = "blank {0} stops the context from starting")
    @CsvSource({
            "integration.python.base-url, baseUrl",
            "integration.python.auth-token, authToken"
    })                                                                             // T17: 2 executions
    void aBlankSettingStopsTheContextFromStarting(String blankProperty, String fieldName) {
        runner.withPropertyValues(
                        "integration.python.base-url=http://python.test:8082",
                        "integration.python.auth-token=secret-token",
                        blankProperty + "=")                                        // a later value for the same name wins: now blank
                .run(context -> {
                    assertThat(context).hasFailed();
                    // The start-up failure is a chain of exceptions; the bottom one says which field broke the rule.
                    assertThat(context).getFailure().hasStackTraceContaining(fieldName);
                });
    }
}