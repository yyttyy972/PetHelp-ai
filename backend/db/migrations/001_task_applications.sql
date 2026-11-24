BEGIN;
CREATE TABLE IF NOT EXISTS "TaskApplication" (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    deleted_at timestamptz,
    request_id uuid NOT NULL REFERENCES "ServiceRequest"(id),
    helper_id uuid NOT NULL REFERENCES "HelperProfile"(id),
    request_version integer NOT NULL CHECK (request_version > 0),
    status varchar(20) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending','accepted','rejected','withdrawn')),
    note text NOT NULL DEFAULT '',
    scheduled_start timestamptz NOT NULL,
    scheduled_end timestamptz NOT NULL,
    agreed_fee numeric(10,2) NOT NULL CHECK (agreed_fee >= 0),
    booking_id uuid REFERENCES "Booking"(id),
    CHECK (scheduled_end > scheduled_start),
    CHECK ((status = 'accepted') = (booking_id IS NOT NULL))
);
CREATE UNIQUE INDEX IF NOT EXISTS task_application_pending_unique
ON "TaskApplication"(request_id, helper_id, request_version)
WHERE status='pending' AND deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS task_application_helper ON "TaskApplication"(helper_id);
CREATE INDEX IF NOT EXISTS task_application_request ON "TaskApplication"(request_id);
COMMIT;
