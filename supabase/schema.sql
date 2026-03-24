-- ── Auth tables ─────────────────────────────────

create table if not exists users (
    id bigserial primary key,
    email varchar(255) not null unique,
    password_hash text not null,
    role varchar(20) not null default 'officer',
    is_active boolean not null default true,
    totp_secret varchar(64),
    totp_verified boolean not null default false,
    created_at timestamptz default now(),
    updated_at timestamptz
);

create table if not exists officers (
    id bigserial primary key,
    user_id bigint not null unique references users(id) on delete cascade,
    full_name varchar(255) not null,
    rank varchar(100),
    id_number varchar(100) not null unique,
    work_station varchar(100) not null,
    access_type varchar(30) not null,
    created_at timestamptz default now(),
    updated_at timestamptz
);

create index if not exists idx_users_email on users(email);
create index if not exists idx_officers_id_number on officers(id_number);

-- ── Biometric tables ───────────────────────────

create table if not exists persons (
    id bigserial primary key,
    person_id varchar(64) not null unique,
    full_name varchar(255),
    email varchar(255),
    mobile_number varchar(50),
    address text,
    criminal_records text,
    face_image_key text,
    face_image_url text,
    created_at timestamptz default now(),
    updated_at timestamptz
);

create table if not exists face_embeddings (
    id bigserial primary key,
    person_id varchar(64) not null unique references persons(person_id) on delete cascade,
    embedding json not null,
    created_at timestamptz default now()
);

create table if not exists fingerprint_templates (
    id bigserial primary key,
    person_id varchar(64) not null unique references persons(person_id) on delete cascade,
    template json not null,
    capture_method varchar(30) not null default 'image_upload',
    created_at timestamptz default now()
);

create index if not exists idx_persons_person_id on persons(person_id);
create index if not exists idx_face_embeddings_person_id on face_embeddings(person_id);
create index if not exists idx_fingerprint_templates_person_id on fingerprint_templates(person_id);
