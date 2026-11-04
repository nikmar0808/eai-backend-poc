package com.utility.ingestion.client;

import com.utility.ingestion.api.dto.BulkIngestionRequest;
import com.utility.ingestion.api.dto.TransformationResponse;

/**
 * The gateway's view of the transformation service. The service layer depends on this abstraction, so a test can
 * supply a stand-in and the transport (HTTP today) can change without touching the service.
 */
public interface TransformationGateway {

    /** The key may be null: a client need not send one. */
    TransformationResponse transform(BulkIngestionRequest request, String idempotencyKey);
}