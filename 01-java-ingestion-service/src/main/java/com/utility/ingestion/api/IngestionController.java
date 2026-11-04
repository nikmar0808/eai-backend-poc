package com.utility.ingestion.api;

import com.utility.ingestion.api.dto.BulkIngestionRequest;
import com.utility.ingestion.api.dto.TransformationResponse;
import com.utility.ingestion.service.IngestionService;
import jakarta.validation.Valid;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.regex.Pattern;

@RestController
@RequestMapping("/api/v1/ingest")
public class IngestionController {

    /** The contract's rule: 1 to 64 visible ASCII characters. */
    private static final Pattern IDEMPOTENCY_KEY = Pattern.compile("[\\x21-\\x7E]{1,64}");

    private final IngestionService ingestionService;

    public IngestionController(IngestionService ingestionService) {
        this.ingestionService = ingestionService;
    }

    @PostMapping("/bulk")
    public ResponseEntity<TransformationResponse> ingest(
            @Valid @RequestBody BulkIngestionRequest request,
            @RequestHeader(name = "Idempotency-Key", required = false) String idempotencyKey) {
        // Checked by hand. A constraint annotation on this parameter would switch Spring to method validation, which
        // reports the body's errors as a different exception, and would change every 400 of this route.
        if (idempotencyKey != null && !IDEMPOTENCY_KEY.matcher(idempotencyKey).matches()) {
            throw new InvalidIdempotencyKeyException();
        }
        return ResponseEntity.ok(ingestionService.ingest(request, idempotencyKey));
    }
}