BEGIN;

CREATE TABLE IF NOT EXISTS "Address" (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 created_at timestamptz NOT NULL DEFAULT now(),
 updated_at timestamptz NOT NULL DEFAULT now(),
 deleted_at timestamptz,
 user_id uuid NOT NULL REFERENCES "User"(id),
 label varchar(30) NOT NULL,
 contact_name varchar(50) NOT NULL,
 contact_phone varchar(30) NOT NULL,
 address text NOT NULL CHECK(length(address) BETWEEN 2 AND 300),
 latitude double precision CHECK(latitude BETWEEN -90 AND 90),
 longitude double precision CHECK(longitude BETWEEN -180 AND 180),
 is_default boolean NOT NULL DEFAULT false
);
CREATE INDEX IF NOT EXISTS address_user_active ON "Address"(user_id) WHERE deleted_at IS NULL;
CREATE UNIQUE INDEX IF NOT EXISTS address_one_default ON "Address"(user_id) WHERE is_default AND deleted_at IS NULL;

ALTER TABLE "ChatMessage" ADD COLUMN IF NOT EXISTS kind varchar(20) NOT NULL DEFAULT 'text';
ALTER TABLE "ChatMessage" ADD COLUMN IF NOT EXISTS media_url text;
ALTER TABLE "ChatMessage" ADD COLUMN IF NOT EXISTS latitude double precision;
ALTER TABLE "ChatMessage" ADD COLUMN IF NOT EXISTS longitude double precision;
ALTER TABLE "ChatMessage" ADD COLUMN IF NOT EXISTS accuracy_m double precision;
ALTER TABLE "ChatMessage" ADD COLUMN IF NOT EXISTS location_label varchar(200);
ALTER TABLE "ChatMessage" DROP CONSTRAINT IF EXISTS "ChatMessage_content_check";
ALTER TABLE "ChatMessage" ALTER COLUMN content DROP NOT NULL;
ALTER TABLE "ChatMessage" ADD CONSTRAINT chat_message_payload CHECK (
 (kind='text' AND content IS NOT NULL AND length(content) BETWEEN 1 AND 2000) OR
 (kind='audio' AND media_url IS NOT NULL) OR
 (kind='location' AND latitude BETWEEN -90 AND 90 AND longitude BETWEEN -180 AND 180)
);

CREATE TABLE IF NOT EXISTS "CallSignal" (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 seq bigint GENERATED ALWAYS AS IDENTITY UNIQUE,
 created_at timestamptz NOT NULL DEFAULT now(),
 booking_id uuid NOT NULL REFERENCES "Booking"(id),
 sender_id uuid NOT NULL REFERENCES "User"(id),
 call_id uuid NOT NULL,
 kind varchar(20) NOT NULL CHECK(kind IN ('offer','answer','ice','hangup')),
 payload jsonb NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS call_signal_booking_seq ON "CallSignal"(booking_id,seq);

COMMIT;
