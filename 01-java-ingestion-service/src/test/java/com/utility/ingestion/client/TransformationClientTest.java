package com.utility.ingestion.client;

import com.utility.ingestion.TestData;
import com.utility.ingestion.api.dto.TransformationResponse;
import com.utility.ingestion.configuration.IntegrationProperties;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpMethod;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.web.client.HttpClientErrorException;
import org.springframework.web.client.HttpServerErrorException;
import org.springframework.web.client.ResourceAccessException;
import org.springframework.web.client.RestClient;

import java.io.IOException;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.header;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.method;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.requestTo;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withException;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withStatus;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withSuccess;

class TransformationClientTest {

    private static final String TRANSFORM_URL = "http://python.test/api/v1/transform";

    private MockRestServiceServer server;
    private TransformationClient client;

    @BeforeEach
    void setUp() {
        RestClient.Builder builder = RestClient.builder();
        server = MockRestServiceServer.bindTo(builder).build();
        client = new TransformationClient(builder, new IntegrationProperties("http://python.test", "test-token"));
    }

    @Test
    void sendsTheTokenToTheTransformEndpointAndMapsTheResponse() {
        server.expect(requestTo(TRANSFORM_URL))
                .andExpect(method(HttpMethod.POST))
                .andExpect(header("X-EAI-TOKEN", "test-token"))
                .andRespond(withSuccess(TestData.PYTHON_RESPONSE_JSON, MediaType.APPLICATION_JSON));

        TransformationResponse response = client.transform(TestData.validRequest());

        assertThat(response.message()).isEqualTo("ok");
        assertThat(response.metadata().processedAsset()).isEqualTo("MTR-POC2-001");
        assertThat(response.metadata().intervalsSaved()).isEqualTo(1);
        assertThat(response.analyticsSummary().cumulativeKwh()).isEqualTo(12.5);
        server.verify();
    }

    @Test
    void makesExactlyOneCallWhenTheServiceFails() {
        // Finding D1 (retry loop) is fixed. If a retry is ever reintroduced, the mock server rejects the
        // second request ("No further requests expected") and this test fails.
        server.expect(requestTo(TRANSFORM_URL)).andRespond(withStatus(HttpStatus.INTERNAL_SERVER_ERROR));

        assertThatThrownBy(() -> client.transform(TestData.validRequest()))
                .isInstanceOf(HttpServerErrorException.class);
        server.verify();
    }

    @Test
    void aRejectionByTheServiceSurfacesAsAClientErrorException() {
        server.expect(requestTo(TRANSFORM_URL)).andRespond(withStatus(HttpStatus.UNPROCESSABLE_ENTITY));

        assertThatThrownBy(() -> client.transform(TestData.validRequest()))
                .isInstanceOf(HttpClientErrorException.class)
                .extracting(e -> ((HttpClientErrorException) e).getStatusCode().value())
                .isEqualTo(422);
        server.verify();
    }

    @Test
    void anUnreachableServiceSurfacesAsAResourceAccessException() {
        server.expect(requestTo(TRANSFORM_URL)).andRespond(withException(new IOException("connection refused")));

        assertThatThrownBy(() -> client.transform(TestData.validRequest()))
                .isInstanceOf(ResourceAccessException.class);
        server.verify();
    }
}
