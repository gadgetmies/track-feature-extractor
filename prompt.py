#! /usr/bin/env python

import sys
import shlex
import sounddevice as sd
import wavio as wv
from essentia.standard import MonoLoader, TensorflowPredictEffnetDiscogs
from configparser import ConfigParser
import psycopg2 as psycopg2
import traceback
from tabulate import tabulate
from datetime import date

current_year = int(date.today().strftime("%Y"))
earliest_year = 1900
bpm = None
key = None
key_format = 'camelot'
keys = {
    'camelot': ['1A', '2A', '3A', '4A', '5A', '6A', '7A', '8A', '9A', '10A', '11A', '12A', '1B', '2B', '3B', '4B', '5B',
                '6B', '7B', '8B', '9B', '10B', '11B', '12B'],
    'openkey': ['6m', '7m', '8m', '9m', '10m', '11m', '12m', '1m', '2m', '3m', '4m', '5m', '6d', '7d', '8d', '9d',
                '10d', '11d', '12d', '1d', '2d', '3d', '4d', '5d'],
    'standard': ['Abm', 'Ebm', 'Bbm', 'Fm', 'Cm', 'Gm', 'Dm', 'Am', 'Em', 'Bm', 'F#m', 'Dbm', 'B', 'F#', 'Db', 'Ab',
                 'Eb', 'Bb', 'F', 'C', 'G', 'D', 'A', 'E']
}


def print_commands():
    print('''
Usage
-----
a:       Select audio device
f:       Set key format (standard, camelot, openkey)

b 140:   Set BPM to 140
k 1A:    Set current key to 1A (you can use OpenKey (1m), Camelot (1A) and standard keys (Abm))
y:       Set earliest release year filter

<enter>: Record and find suitable tracks using the set key and BPM as well as the features extracted from input
s query: Search for track matching 'query'
s 1:     Search for compatible tracks for track with index 1 in the most recent track search results
s:       Search for compatible tracks for currently selected track with updated filters
l:       List the most recent track search results               
q:       Quit
    ''')


key_formats = list(keys.keys())
results = []
selected_track = {}


def load_config(filename='database.ini', section='postgresql'):
    parser = ConfigParser()
    parser.read(filename)

    # get section, default to postgresql
    config = {}
    if parser.has_section(section):
        params = parser.items(section)
        for param in params:
            config[param[0]] = param[1]
    else:
        raise Exception('Section {0} not found in the {1} file'.format(section, filename))
    return config


def connect(config):
    """ Connect to the PostgreSQL database server """
    try:
        # connecting to the PostgreSQL server
        with psycopg2.connect(**config) as conn:
            print('Connected to the PostgreSQL server.')
            return conn
    except (psycopg2.DatabaseError, Exception) as error:
        print(error)


def select_key_format():
    print("""
1: camelot
2: openkey
3: standard
""")
    kf = ''
    while True:
        try:
            val = input('Key format number > ')
            return key_formats[int(val) - 1]
        except Exception as x:
            print(x)
            print("ERROR: Invalid selection. Please provide a single number.")


def select_audio_device():
    while True:
        devices = sd.query_devices()
        print(devices)
        selected = input('Input device number > ')
        try:
            sd.default.device = int(selected)
            return
        except Exception as x:
            print(x)
            print('ERROR: Unable to parse input. Please provide a single number.')


result_headers = ['#', 'ID', 'Artist', 'Title', 'Comment', 'BPM', 'Key']


def search(query):
    with conn.cursor() as cur:
        try:
            cur.execute(f"""
SELECT track_id AS id, track_artist AS artist, track_title AS title, track_comment as comment, track_bpm AS bpm, track_key AS key
FROM track
WHERE
  TO_TSVECTOR(
          'simple',
          unaccent(track_title || ' ' ||
                   COALESCE(track_title, '') || ' ' ||
                   COALESCE(track_artist, ' ') || ' ' ||
                   COALESCE(track_album, ' ') || ' ' ||
                   COALESCE(track_label, ''))) @@
  websearch_to_tsquery('simple', unaccent('{query}'))
LIMIT 20
            """)
            records = cur.fetchall()
            cur.close()
            return records

        except(psycopg2.DatabaseError, Exception) as error:
            print("Search failed:")
            print(error)
            cur.close()
            return []


def select_track(results):
    while True:
        selected = input('Track number > ')
        try:
            track_number = int(selected)
            if track_number < 0 or track_number >= len(results):
                print(f"ERROR: Invalid track number. Please provide number between 1-{len(results) - 1}")
                continue
            return results[track_number]
        except Exception as x:
            print(x)
            print(f'ERROR: Unable to parse input. Please provide a single track number between 1-{len(results) - 1}')


def find_suitable_tracks(selected_track):
    with conn.cursor() as cur:
        suitable_keys = keys['camelot']
        if key is not None:
            num = int(keys['camelot'][key][0:-1])
            next_num = (num + 1) % 12
            prev_num = (num - 1)
            if prev_num < 1:
                prev_num += 12
            suitable_keys = [f'{num}A', f'{num}B', f'{next_num}A', f'{next_num}B', f'{prev_num}A', f'{prev_num}B']
        try:
            cur.execute(f"""
WITH selected_track AS (
    SELECT track_embedding_vector, track_artist 
    FROM track_embedding NATURAL JOIN track 
    WHERE track_id = %s AND track_embedding_type = 'multi'
)
SELECT track_id AS id, t.track_artist AS artist, track_title AS title, track_comment AS comment, track_bpm AS bpm, track_key AS key
FROM track t NATURAL JOIN track_embedding te, selected_track
WHERE
    track_id <> %s
    AND track_key = ANY(%s)
    AND (%s IS NULL OR (ABS(1 - track_bpm / %s) < 0.1 OR ABS(1 - track_bpm * 2 / %s) < 0.1 OR ABS(1 - track_bpm / (%s * 2)) < 0.1))    AND t.track_artist <> selected_track.track_artist
    AND track_release_date > to_date(%s::text, 'YYYY')
ORDER BY
    te.track_embedding_vector <-> selected_track.track_embedding_vector 
LIMIT 20
                    """, [selected_track[0], selected_track[0], suitable_keys, bpm, bpm, bpm, bpm, earliest_year])
            records = cur.fetchall()
            cur.close()
            return records

        except (psycopg2.DatabaseError, Exception) as error:
            print(error)
            traceback.print_exc()
            cur.close()
            conn.rollback()


def similarity_search():
    sampling_frequency = 44100
    duration = 5
    print("Recording")
    recording = sd.rec(int(duration * sampling_frequency), samplerate=sampling_frequency, channels=2)
    sd.wait()
    wv.write("output.wav", recording, sampling_frequency, sampwidth=2)
    print("Recording done, analyzing...")
    print("Preparing audio")
    audio = MonoLoader(filename='./output.wav', sampleRate=16000, resampleQuality=4)()
    print("Preparing model")
    model = TensorflowPredictEffnetDiscogs(graphFilename=f"discogs_multi_embeddings-effnet-bs64-1.pb",
                                           output="PartitionedCall:1")
    print("Processing audio")
    embeddings = model(audio)
    print("Analysis done, searching...")
    with conn.cursor() as cur:
        suitable_keys = keys['camelot']
        if key is not None:
            num = int(keys['camelot'][key][0:-1])
            next_num = (num + 1) % 12
            prev_num = (num - 1)
            if prev_num < 1:
                prev_num += 12
            suitable_keys = [f'{num}A', f'{num}B', f'{next_num}A', f'{next_num}B', f'{prev_num}A', f'{prev_num}B']
        try:
            cur.execute(f"""
SELECT track_id AS id, track_artist AS artist, track_title AS title, track_comment AS comment, track_bpm AS bpm, track_key AS key
FROM track NATURAL JOIN track_embedding
WHERE 
    track_key = ANY(%s)
    AND (%s IS NULL OR (ABS(1 - track_bpm / %s) < 0.1 OR ABS(1 - track_bpm * 2 / %s) < 0.1 OR ABS(1 - track_bpm / (%s * 2)) < 0.1))
    AND track_release_date > to_date(%s::text, 'YYYY')
ORDER BY
    track_embedding_vector <-> '{embeddings.T.mean(1).tolist()}'
LIMIT 20
            """, [suitable_keys, bpm, bpm, bpm, bpm, earliest_year])
            records = cur.fetchall()
            cur.close()
            print(tabulate(records, headers=result_headers, tablefmt="psql", showindex="always"))
            return records

        except (psycopg2.DatabaseError, Exception) as error:
            print(error)
            traceback.print_exc()
            cur.close()


if __name__ == '__main__':
    config = load_config()
    conn = connect(config)
    print_commands()
    while True:
        devices = sd.query_devices()
        user_input = input(
            f'{devices[sd.default.device[1]]["name"]} {bpm if bpm else "any_BPM"} {keys[key_format][key] if key else "any_key"} >{earliest_year} >>> ')
        if user_input == '':
            results = similarity_search()
            continue

        cmd, *args = shlex.split(user_input)

        if cmd == 'b':
            bpm = args[0]

        elif cmd == 'a':
            select_audio_device()

        elif cmd == 's':
            search_results = []
            if len(args) == 0 or (len(args) == 1 and args[0].isnumeric()):
                if len(args) == 1:
                    index = int(args[0])
                    result_count = len(results)
                    if result_count == 0:
                        print(
                            'ERROR: No tracks to choose from. Please run text search (s command) or similarity search \
(empty command) first')
                        continue
                    elif index > result_count:
                        print(f'ERROR: track index out of bounds. Please provide value between 0 and {result_count}')
                        continue
                    selected_track = results[index]
                    if selected_track[4]:
                        bpm = selected_track[4]
                    if selected_track[5]:
                        key = keys['camelot'].index(selected_track[5])

                maybe_comment = selected_track[3]
                print(
                    f"Selected track: {selected_track[1]} - {selected_track[2]} \
{f'({maybe_comment})' if maybe_comment else ''} [{selected_track[4]} {selected_track[5]}]")
                search_results = find_suitable_tracks(selected_track)
            else:
                search_results = search(' '.join(args))

            if len(search_results) > 1:
                print(tabulate(search_results, headers=result_headers, tablefmt="psql", showindex="always"))
                results = search_results
            else:
                print("No suitable tracks found")

        elif cmd == 'f':
            key_format = select_key_format()

        elif cmd == 'k':
            try:
                key = keys[key_format].index(args[0])
            except Exception as x:
                print(x)
                print(f"ERROR: Invalid selection. Please provide {key_format} key")

        elif cmd == 'l':
            print(tabulate(results, headers=result_headers, tablefmt="psql", showindex="always"))

        elif cmd == 'y':
            try:
                year = int(args[0])
                if (year < 1900 or year > current_year):
                    print("ERROR: Invalid year provided. Please provide value between the current year and 1900")
                earliest_year = year
            except Exception as x:
                print(x)
                print("ERROR: Invalid year provided. Please provide value between the current year and 1900")

        elif cmd == 'q':
            print('Bye!')
            exit(0)

        else:
            if cmd != '?':
                print("Invalid command")
            print_commands()
