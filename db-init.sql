create
extension vector;

create
extension if not exists unaccent;

create table track
(
    track_id           serial primary key,
    track_path         text UNIQUE,
    track_artist       text,
    track_title        text,
    track_comment      text,
    track_isrc         text,
    track_key          text,
    track_bpm          numeric,
    track_genre        text,
    track_energy       numeric,
    track_release_date date,
    track_album        text,
    track_label        text
);

create type embedding_type as enum ('artist', 'multi');
create table track_embedding
(
    track_id               integer references track (track_id) ON DELETE CASCADE UNIQUE NOT NULL,
    track_embedding_vector vector(1280) not null,
    track_embedding_type   embedding_type                                               not null,
    unique (track_id, track_embedding_type)
);

create table track_spotify_audio_features
(
    track_id                     integer references track (track_id) ON DELETE CASCADE UNIQUE NOT NULL,
    track_spotify_audio_features JSON                                                         NOT NULL
);