package com.utility.ingestion.api;

/** The Idempotency-Key header breaks its rule. Carries no message: the handler's sentence is fixed, and quotes no input. */
public class InvalidIdempotencyKeyException extends RuntimeException {
}