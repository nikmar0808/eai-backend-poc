package com.utility.ingestion.service;

import com.utility.ingestion.api.dto.BulkIngestionRequest;
import com.utility.ingestion.api.dto.TransformationResponse;
import com.utility.ingestion.client.TransformationGateway;

import org.springframework.stereotype.Service;

@Service
public class IngestionService {

    private final TransformationGateway transformationGateway;

    public IngestionService(TransformationGateway transformationGateway) {
        this.transformationGateway = transformationGateway;
    }

    /** The key may be null: a client need not send one. */
    public TransformationResponse ingest(BulkIngestionRequest request, String idempotencyKey) {
        return transformationGateway.transform(request, idempotencyKey);
    }
}