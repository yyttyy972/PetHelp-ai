BEGIN;
CREATE TABLE IF NOT EXISTS "ChatMessage" (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 seq bigint GENERATED ALWAYS AS IDENTITY UNIQUE,
 created_at timestamptz NOT NULL DEFAULT now(),
 updated_at timestamptz NOT NULL DEFAULT now(), deleted_at timestamptz,
 booking_id uuid NOT NULL REFERENCES "Booking"(id),
 sender_id uuid NOT NULL REFERENCES "User"(id),
 client_id uuid NOT NULL,
 content text NOT NULL CHECK(length(content) BETWEEN 1 AND 2000),
 read_at timestamptz,
 UNIQUE(sender_id,client_id)
);
CREATE INDEX IF NOT EXISTS chat_booking_seq ON "ChatMessage"(booking_id,seq);
COMMIT;
