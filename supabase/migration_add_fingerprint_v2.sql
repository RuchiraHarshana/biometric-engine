-- Experimental fingerprint module storage (isolated from fingerprint_templates)

create table if not exists fingerprint_templates_v2 (
    id bigserial primary key,
    person_id varchar(64) not null references persons(person_id) on delete cascade,
    finger_label varchar(32) not null,
    template json not null,
    capture_method varchar(30) not null default 'image_upload',
    algorithm varchar(30) not null default 'akaze_v2',
    quality_score double precision,
    created_at timestamptz default now(),
    updated_at timestamptz default now(),
    unique (person_id, finger_label)
);

create index if not exists idx_fingerprint_templates_v2_person_id
    on fingerprint_templates_v2(person_id);

create index if not exists idx_fingerprint_templates_v2_finger_label
    on fingerprint_templates_v2(finger_label);
