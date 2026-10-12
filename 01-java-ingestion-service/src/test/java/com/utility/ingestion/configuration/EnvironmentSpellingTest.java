package com.utility.ingestion.configuration;

import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.boot.test.context.ConfigDataApplicationContextInitializer;
import org.springframework.boot.test.context.runner.ApplicationContextRunner;
import org.springframework.core.env.StandardEnvironment;
import org.springframework.core.env.SystemEnvironmentPropertySource;

import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

class EnvironmentSpellingTest {

    /**
     * The dev compose file sets INTEGRATION_PYTHON_BASE_URL (underscore); the production compose file and the Azure
     * documents use INTEGRATION_PYTHON_BASE-URL (hyphen). Verified against application.properties: both placeholders
     * there are hyphenated (${INTEGRATION_PYTHON_BASE-URL:...}), and Spring's system-environment lookup retries a
     * hyphenated name with the hyphen replaced by an underscore, so the first two spellings are honoured through the
     * placeholder. The third is honoured through Spring Boot's own relaxed binding of the property
     * integration.python.base-url, which applies only to a property source named "systemEnvironment"; the fake
     * environment below therefore takes that name (and replaces the real one inside this test context).
     * A failing row is a finding, not a test bug: record it as a finding against the compose file concerned.
     */
    @ParameterizedTest(name = "environment variable {0} is honoured")
    @ValueSource(strings = {"INTEGRATION_PYTHON_BASE_URL", "INTEGRATION_PYTHON_BASE-URL", "INTEGRATION_PYTHON_BASEURL"})
    void baseUrlEnvironmentVariableSpellings(String variable) {
        new ApplicationContextRunner()
                .withInitializer(context -> context.getEnvironment().getPropertySources().addFirst(
                        new SystemEnvironmentPropertySource(StandardEnvironment.SYSTEM_ENVIRONMENT_PROPERTY_SOURCE_NAME, Map.of(
                                variable, "http://from-env.test",
                                "INTEGRATION_PYTHON_AUTH_TOKEN", "token-from-env"))))
                .withInitializer(new ConfigDataApplicationContextInitializer())
                .withUserConfiguration(AppConfiguration.class)
                .run(context -> assertThat(context.getBean(IntegrationProperties.class).baseUrl())
                        .isEqualTo("http://from-env.test"));
    }
}
