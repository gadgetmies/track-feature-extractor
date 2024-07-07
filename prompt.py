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


def print_commands():
    print('''
Usage
-----
<enter>: Record and find suitable tracks using the set key and BPM as well as the features extracted from input
b 140:   Set BPM to 140
k 1A:    Set current key to 1A (you can use OpenKey (1m), Camelot (1A) and standard keys (Abm))
f:       Set key format (standard, camelot, openkey)
a:       Select audio device
q:       Quit
    ''')


bpm = 140
key = 0
key_format = 'camelot'
keys = {
    'camelot': ['1A', '2A', '3A', '4A', '5A', '6A', '7A', '8A', '9A', '10A', '11A', '12A', '1B', '2B', '3B', '4B', '5B',
                '6B', '7B', '8B', '9B', '10B', '11B', '12B'],
    'openkey': ['6m', '7m', '8m', '9m', '10m', '11m', '12m', '1m', '2m', '3m', '4m', '5m', '6d', '7d', '8d', '9d',
                '10d', '11d', '12d', '1d', '2d', '3d', '4d', '5d'],
    'standard': ['Abm', 'Ebm', 'Bbm', 'Fm', 'Cm', 'Gm', 'Dm', 'Am', 'Em', 'Bm', 'F#m', 'Dbm', 'B', 'F#', 'Db', 'Ab',
                 'Eb', 'Bb', 'F', 'C', 'G', 'D', 'A', 'E']
}
key_formats = list(keys.keys())


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


def record_audio():
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
    print(embeddings)
    print("Analysis done, searching...")
    with conn.cursor() as cur:
        num = int(keys['camelot'][key][0:-1])
        next_num = (num + 1) % 12
        prev_num = (num - 1)
        if prev_num < 1:
            prev_num += 12
        suitable_keys = [f'{num}A', f'{num}B', f'{next_num}A', f'{next_num}B', f'{prev_num}A', f'{prev_num}B']
        try:
            cur.execute(f"""
SELECT track_artist AS artist, track_title AS title, track_bpm AS bpm, track_key AS key
FROM track NATURAL JOIN track_embedding
WHERE 
    track_key = ANY(%s)
    AND ABS(1 - track_bpm / %s) < 0.1
ORDER BY
    track_embedding_vector <-> '{embeddings.T.mean(1).tolist()}'
LIMIT 20
            """, [suitable_keys, bpm])
            records = cur.fetchall()
            print(tabulate(records, headers="keys", tablefmt="psql"))

        except (psycopg2.DatabaseError, Exception) as error:
            print(error)
            traceback.print_exc()
            cur.close()
            conn.rollback()


if __name__ == '__main__':
    config = load_config()
    conn = connect(config)
    print_commands()
    while True:
        devices = sd.query_devices()
        user_input = input(f'{devices[sd.default.device[1]]["name"]} {bpm} {keys[key_format][key]} > ')
        if user_input == '':
            record_audio()
            continue

        cmd, *args = shlex.split(user_input)

        if cmd == 'b':
            bpm = args[0]

        elif cmd == 'a':
            select_audio_device()

        elif cmd == 'f':
            key_format = select_key_format()

        elif cmd == 'k':
            try:
                key = keys[key_format].index(args[0])
            except Exception as x:
                print(x)
                print(f"ERROR: Invalid selection. Please provide {key_format} key")

        elif cmd == 'q':
            print('Bye!')
            exit(0)

        else:
            if cmd != '?':
                print("Invalid command")
            print_commands()
