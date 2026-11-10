-- PostgreSQL 17; apply once to an empty database.

BEGIN;

SET TIME ZONE 'UTC';

CREATE TYPE role_type AS ENUM ('owner','helper');

CREATE TYPE pet_species AS ENUM ('cat','dog');

CREATE TYPE service_type AS ENUM ('home_visit','dog_walking','errand_buy');

CREATE TYPE task_status AS ENUM ('draft','pending_match','pending_confirm','reserved','in_service','pending_verify','completed','cancelled','exception');

CREATE TYPE booking_status AS ENUM ('pending_confirm','reserved','in_service','pending_verify','completed','cancelled','exception');

CREATE TYPE item_status AS ENUM ('pending','completed','blocked','waived');

CREATE TYPE record_kind AS ENUM ('item_completed','pickup','departure','return','purchase','delivery');

CREATE TYPE exception_reason AS ENUM ('cannot_enter','pet_hiding','service_timeout','over_budget','out_of_stock','verification_dispute','other');

CREATE TYPE exception_status AS ENUM ('open','resolved');

CREATE TYPE settlement_status AS ENUM ('unsettled','simulated_settled');

CREATE TYPE verification_status AS ENUM ('unverified','verified');

CREATE TYPE fee_type AS ENUM ('free','paid');

CREATE TYPE fee_pref AS ENUM ('free','paid','both');

CREATE TABLE "User" (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  deleted_at timestamptz,
  account varchar(100) NOT NULL UNIQUE,
  password_hash text NOT NULL,
  display_name varchar(60) NOT NULL,
  avatar_url varchar(255),
  address text,
  verification_status varchar(20) NOT NULL DEFAULT 'unverified' CHECK (verification_status IN ('unverified','verified')),
  roles role_type[] NOT NULL,
  community_code varchar(32) NOT NULL,
  CHECK (length(trim(display_name))>0),
  CHECK (cardinality(roles)>0)
);

CREATE TABLE "PetProfile" (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  deleted_at timestamptz,
  owner_id uuid NOT NULL REFERENCES "User"(id) ON DELETE RESTRICT,
  name varchar(60) NOT NULL,
  species pet_species NOT NULL,
  breed varchar(60),
  birth_date date NOT NULL,
  temperament text,
  precautions text,
  supplies_location text,
  care_instructions text,
  photo_url varchar(255)
);

CREATE TABLE "HelperProfile" (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  deleted_at timestamptz,
  user_id uuid NOT NULL UNIQUE REFERENCES "User"(id) ON DELETE RESTRICT,
  service_types service_type[] NOT NULL,
  service_area text NOT NULL,
  experience text NOT NULL,
  supported_species pet_species[] NOT NULL,
  service_radius_m integer NOT NULL,
  fee_pref varchar(20) NOT NULL DEFAULT 'both' CHECK (fee_pref IN ('free','paid','both')),
  verification_status varchar(20) NOT NULL DEFAULT 'unverified' CHECK (verification_status IN ('unverified','verified')),
  address_tag varchar(50),
  CHECK (cardinality(service_types)>0),
  CHECK (cardinality(supported_species)>0),
  CHECK (service_radius_m>0)
);

CREATE TABLE "Availability" (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  deleted_at timestamptz,
  helper_id uuid NOT NULL REFERENCES "HelperProfile"(id) ON DELETE RESTRICT,
  start_at timestamptz NOT NULL,
  end_at timestamptz NOT NULL,
  CHECK (end_at>start_at)
);

CREATE TABLE "ServiceRequest" (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  deleted_at timestamptz,
  owner_id uuid NOT NULL REFERENCES "User"(id) ON DELETE RESTRICT,
  service_type service_type NOT NULL,
  community_code varchar(32) NOT NULL,
  window_start timestamptz NOT NULL,
  window_end timestamptz NOT NULL,
  expected_duration_minutes integer NOT NULL,
  location text NOT NULL,
  budget decimal(10,2) NOT NULL,
  handover_notes text NOT NULL,
  emergency_contact text NOT NULL,
  requirements text,
  fee_type varchar(20) NOT NULL CHECK (fee_type IN ('free','paid')),
  precautions text,
  raw_text text,
  version integer NOT NULL DEFAULT 1,
  status task_status NOT NULL DEFAULT 'draft',
  CHECK (window_end>window_start),
  CHECK (expected_duration_minutes>0),
  CHECK (expected_duration_minutes*60<=extract(epoch from window_end-window_start)),
  CHECK (budget>=0),
  CHECK (version>0)
);

CREATE TABLE "ChecklistItem" (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  deleted_at timestamptz,
  request_id uuid NOT NULL REFERENCES "ServiceRequest"(id) ON DELETE RESTRICT,
  pet_id uuid REFERENCES "PetProfile"(id) ON DELETE RESTRICT,
  request_version integer NOT NULL,
  item_key varchar(60) NOT NULL,
  position integer NOT NULL,
  content text NOT NULL,
  completion_condition text NOT NULL,
  required boolean NOT NULL DEFAULT true,
  execution_status item_status NOT NULL DEFAULT 'pending',
  product_name varchar(160),
  quantity integer,
  unit varchar(20),
  CHECK (request_version>0),
  CHECK (position>0),
  CHECK (quantity IS NULL OR quantity>0),
  CHECK (num_nonnulls(product_name,quantity,unit) IN (0,3)),
  UNIQUE (request_id,request_version,item_key),
  UNIQUE (request_id,request_version,position)
);

CREATE TABLE "RequestPet" (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  deleted_at timestamptz,
  request_id uuid NOT NULL REFERENCES "ServiceRequest"(id) ON DELETE RESTRICT,
  pet_id uuid NOT NULL REFERENCES "PetProfile"(id) ON DELETE RESTRICT,
  UNIQUE (request_id,pet_id)
);

CREATE TABLE "Booking" (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  deleted_at timestamptz,
  request_id uuid NOT NULL REFERENCES "ServiceRequest"(id) ON DELETE RESTRICT,
  owner_id uuid NOT NULL REFERENCES "User"(id) ON DELETE RESTRICT,
  helper_id uuid NOT NULL REFERENCES "HelperProfile"(id) ON DELETE RESTRICT,
  request_version integer NOT NULL,
  request_snapshot jsonb NOT NULL CHECK (jsonb_typeof(request_snapshot)='object'),
  scheduled_start timestamptz NOT NULL,
  scheduled_end timestamptz NOT NULL,
  reserved_until timestamptz NOT NULL,
  owner_confirmed_at timestamptz,
  helper_confirmed_at timestamptz,
  status booking_status NOT NULL DEFAULT 'pending_confirm',
  agreed_fee decimal(10,2) NOT NULL,
  actual_cost decimal(10,2),
  settlement_status settlement_status NOT NULL DEFAULT 'unsettled',
  settled_at timestamptz,
  cancel_reason text,
  CHECK (request_version>0),
  CHECK (scheduled_end>scheduled_start),
  CHECK (agreed_fee>=0),
  CHECK (actual_cost IS NULL OR actual_cost>=0),
  CHECK ((settlement_status='simulated_settled')=(settled_at IS NOT NULL AND status='completed'))
);

CREATE TABLE "ExecutionRecord" (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  deleted_at timestamptz,
  booking_id uuid NOT NULL REFERENCES "Booking"(id) ON DELETE RESTRICT,
  checklist_item_id uuid NOT NULL REFERENCES "ChecklistItem"(id) ON DELETE RESTRICT,
  actor_id uuid NOT NULL REFERENCES "User"(id) ON DELETE RESTRICT,
  kind record_kind NOT NULL,
  occurred_at timestamptz NOT NULL,
  note text,
  photo_urls text[] NOT NULL DEFAULT '{}',
  actual_cost decimal(10,2),
  CHECK (coalesce(length(trim(note)),0)>0 OR cardinality(photo_urls)>0),
  CHECK (actual_cost IS NULL OR actual_cost>=0),
  UNIQUE (booking_id,checklist_item_id,kind)
);

CREATE TABLE "ExceptionRecord" (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  deleted_at timestamptz,
  booking_id uuid NOT NULL REFERENCES "Booking"(id) ON DELETE RESTRICT,
  reported_by uuid REFERENCES "User"(id) ON DELETE RESTRICT,
  reason_code exception_reason NOT NULL,
  description text NOT NULL,
  resume_status task_status NOT NULL,
  proposed_change jsonb CHECK (jsonb_typeof(proposed_change)='object'),
  status exception_status NOT NULL DEFAULT 'open',
  resolution text,
  approved_change jsonb CHECK (jsonb_typeof(approved_change)='object'),
  resolved_by uuid REFERENCES "User"(id) ON DELETE RESTRICT,
  resolved_at timestamptz,
  CHECK (resume_status IN ('reserved','in_service','pending_verify')),
  CHECK ((status='open' AND num_nonnulls(resolution,resolved_by,resolved_at)=0) OR (status='resolved' AND num_nonnulls(resolution,resolved_by,resolved_at)=3))
);

CREATE TABLE "Review" (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  deleted_at timestamptz,
  booking_id uuid NOT NULL REFERENCES "Booking"(id) ON DELETE RESTRICT,
  reviewer_id uuid NOT NULL REFERENCES "User"(id) ON DELETE RESTRICT,
  reviewee_id uuid NOT NULL REFERENCES "User"(id) ON DELETE RESTRICT,
  rating smallint NOT NULL,
  comment text,
  CHECK (reviewer_id<>reviewee_id),
  CHECK (rating BETWEEN 1 AND 5),
  UNIQUE (booking_id,reviewer_id)
);

CREATE TABLE "TaskEvent" (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  deleted_at timestamptz,
  request_id uuid NOT NULL REFERENCES "ServiceRequest"(id) ON DELETE RESTRICT,
  booking_id uuid REFERENCES "Booking"(id) ON DELETE RESTRICT,
  actor_id uuid REFERENCES "User"(id) ON DELETE RESTRICT,
  event_type varchar(60) NOT NULL,
  from_status task_status,
  to_status task_status NOT NULL,
  request_version integer NOT NULL,
  payload jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(payload)='object'),
  operation varchar(60) NOT NULL,
  idempotency_key uuid,
  request_hash varchar(64),
  response_snapshot jsonb CHECK (jsonb_typeof(response_snapshot)='object'),
  CHECK (request_version>0),
  CHECK (idempotency_key IS NULL OR (request_hash IS NOT NULL AND response_snapshot IS NOT NULL)),
  UNIQUE (request_id,operation,idempotency_key)
);

CREATE INDEX ON "PetProfile" (owner_id);

CREATE INDEX ON "HelperProfile" (user_id);

CREATE INDEX ON "Availability" (helper_id);

CREATE INDEX ON "ServiceRequest" (owner_id);

CREATE INDEX ON "ChecklistItem" (request_id);

CREATE INDEX ON "ChecklistItem" (pet_id);

CREATE INDEX ON "RequestPet" (request_id);

CREATE INDEX ON "RequestPet" (pet_id);

CREATE INDEX ON "Booking" (request_id);

CREATE INDEX ON "Booking" (owner_id);

CREATE INDEX ON "Booking" (helper_id);

CREATE INDEX ON "ExecutionRecord" (booking_id);

CREATE INDEX ON "ExecutionRecord" (checklist_item_id);

CREATE INDEX ON "ExecutionRecord" (actor_id);

CREATE INDEX ON "ExceptionRecord" (booking_id);

CREATE INDEX ON "ExceptionRecord" (reported_by);

CREATE INDEX ON "ExceptionRecord" (resolved_by);

CREATE INDEX ON "Review" (booking_id);

CREATE INDEX ON "Review" (reviewer_id);

CREATE INDEX ON "Review" (reviewee_id);

CREATE INDEX ON "TaskEvent" (request_id);

CREATE INDEX ON "TaskEvent" (booking_id);

CREATE INDEX ON "TaskEvent" (actor_id);

CREATE UNIQUE INDEX booking_one_active ON "Booking"(request_id) WHERE deleted_at IS NULL AND status<>'cancelled';

CREATE UNIQUE INDEX exception_one_open ON "ExceptionRecord"(booking_id) WHERE deleted_at IS NULL AND status='open';

CREATE INDEX ON "ServiceRequest" (status,window_start);

CREATE INDEX ON "Booking" (helper_id,status,scheduled_start,scheduled_end);

CREATE INDEX ON "Availability" (helper_id,start_at,end_at);

CREATE INDEX ON "TaskEvent" (request_id,created_at,id);

CREATE INDEX ON "ExecutionRecord" (booking_id,occurred_at);

CREATE INDEX ON "ExceptionRecord" (booking_id,status);

COMMIT;
