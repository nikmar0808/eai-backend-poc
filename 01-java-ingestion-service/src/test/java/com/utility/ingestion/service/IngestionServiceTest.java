package com.utility.ingestion.service;

import com.utility.ingestion.TestData;
import com.utility.ingestion.api.dto.BulkIngestionRequest;
import com.utility.ingestion.api.dto.TransformationResponse;
import com.utility.ingestion.client.TransformationGateway;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.web.client.ResourceAccessException;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class IngestionServiceTest {

    @Mock
    private TransformationGateway gateway;

    @InjectMocks
    private IngestionService service;

    @Test
    void delegatesTheRequestAndTheKeyToTheGatewayAndReturnsItsResponse() {
        BulkIngestionRequest request = TestData.validRequest();
        TransformationResponse expected = TestData.response();
        when(gateway.transform(request, "key-1")).thenReturn(expected);

        assertThat(service.ingest(request, "key-1")).isSameAs(expected);
        verify(gateway).transform(request, "key-1");
    }

    @Test
    void doesNotSwallowAFailureOfTheGateway() {
        when(gateway.transform(TestData.validRequest(), null)).thenThrow(new ResourceAccessException("down"));

        assertThatThrownBy(() -> service.ingest(TestData.validRequest(), null))
                .isInstanceOf(ResourceAccessException.class);
    }
}