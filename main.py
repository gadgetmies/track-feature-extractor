from dotenv import load_dotenv
load_dotenv()

from essentia.standard import MonoLoader, TensorflowPredictEffnetDiscogs
from configparser import ConfigParser
import psycopg2 as psycopg2
import argparse
import os
from glob import glob
from pydub import AudioSegment
from tempfile import NamedTemporaryFile
import traceback
import taglib
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import json

spotify = spotipy.Spotify(auth_manager=SpotifyClientCredentials())

# Construct the argument parser
ap = argparse.ArgumentParser()

# Add the arguments to the parser
ap.add_argument("path", help="Path to search mp3 files from")
ap.add_argument("-r", "--recursive", help="Find files recursively", default=True)
ap.add_argument("-m", "--model", choices=['artist', 'multi'], help="Model type", default='artist')
args = ap.parse_args()

print(f"Finding .mp3 files in {args.path}")
tracks = glob(args.path + '/**/*.mp3', recursive=True)
print(f"Found {len(tracks)} files")

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

def safe_get_first_tag_value(dict, key):
  if (key in dict):
    value = dict[key][0].replace("'", "\''")
    return f"'{value}'"
  else:
    return "null"

def pad_date(date):
  if (date == 'null'):
    return date
  length = len(date)
  if (length == 12):
    return date
  elif (length == 9):
    return f"{date[:-1]}-01'"
  elif (length == 6):
    return f"{date[:-1]}-01-01'"
  else:
    raise Exception(f"Unexpected date format: {date}")

def get_tag_info(absoluteFilePath):
  audiofile = taglib.File(absoluteFilePath)
  tags = audiofile.tags
  return {
    'key': safe_get_first_tag_value(tags,"INITIALKEY"),
    'bpm': safe_get_first_tag_value(tags,"BPM"),
    'isrc': safe_get_first_tag_value(tags,"ISRC"),
    'genre': safe_get_first_tag_value(tags,"GENRE"),
    'energy': safe_get_first_tag_value(tags,"ENERGYLEVEL"),
    'date': pad_date(safe_get_first_tag_value(tags,"DATE")),
    'artist': safe_get_first_tag_value(tags,"ARTIST"),
    'title': safe_get_first_tag_value(tags,"TITLE"),
    'album': safe_get_first_tag_value(tags,"ALBUM"),
    'label': safe_get_first_tag_value(tags,"PUBLISHER"),
  }

def get_spotify_details(isrc):
  result = spotify.search(q=f'isrc:{isrc}')
  items = result['tracks']['items']
  if (len(items) > 0):
    id = items[0]['id']
    features = spotify.audio_features([id])
    return features[0]
  else:
    return {}

if __name__ == '__main__':
  config = load_config()
  conn = connect(config)
  print("Connected")

  for filename in tracks:
    absoluteFilePath = os.path.abspath(filename)
    escaped_file_path = absoluteFilePath.replace("'", "\''")
    print(f"Processing: {absoluteFilePath}")
    try:
      print("Querying previous data")
      with conn.cursor() as cur:
        cur.execute(f"""
          SELECT 
            EXISTS (
              SELECT track_id FROM track NATURAL JOIN track_embedding 
              WHERE track_path = '{escaped_file_path}'
                AND track_embedding_type = '{args.model}')
            AND
            EXISTS (
              SELECT track_id FROM track NATURAL JOIN track_spotify_audio_features
              WHERE track_path = '{escaped_file_path}')
            AS metadata_exists
          """)
        if (cur.fetchone()[0]):
          print("Metadata already exists, skipping")
          cur.close()
          continue

      print("Metadata not found, processing file")
      print("Extracting metadata from ID3 tags")
      tags = get_tag_info(absoluteFilePath)

      spotify_details = {}
      isrc = tags['isrc']
      if (isrc != 'null'):
        print(f"Fetching Spotify audio features for ISRC: {isrc}")
        spotify_details = get_spotify_details(isrc[1:-1])
      #outputFile = NamedTemporaryFile()
      print("Converting mp3 to wav")
      sound = AudioSegment.from_mp3(absoluteFilePath)
      sound.export('./output.wav', format="wav")
      print("Preparing audio")
      audio = MonoLoader(filename='./output.wav', sampleRate=16000, resampleQuality=4)()
      print("Preparing model")
      model = TensorflowPredictEffnetDiscogs(graphFilename=f"discogs_{args.model}_embeddings-effnet-bs64-1.pb", output="PartitionedCall:1")
      print("Processing audio")
      embeddings = model(audio)
      print("Storing result in database")
      with conn.cursor() as cur:
        cur.execute(f"""
          INSERT INTO track
            (track_path, track_key, track_bpm, track_isrc, track_genre, track_energy, track_release_date, track_artist, track_title, track_album, track_label)
          VALUES ('{escaped_file_path}', {tags["key"]}, {tags["bpm"]}, {tags["isrc"]}, {tags["genre"]}, {tags["energy"]}, {tags["date"]}, {tags["artist"]}, {tags["title"]}, {tags["album"]}, {tags["label"]})
          ON CONFLICT ON CONSTRAINT track_track_path_key
          DO UPDATE
            SET
              track_key = COALESCE(EXCLUDED.track_key, track.track_key),
              track_bpm = COALESCE(EXCLUDED.track_bpm, track.track_bpm),
              track_isrc = COALESCE(EXCLUDED.track_isrc, track.track_isrc),
              track_genre = COALESCE(EXCLUDED.track_genre, track.track_genre),
              track_energy = COALESCE(EXCLUDED.track_energy, track.track_energy),
              track_release_date = COALESCE(EXCLUDED.track_release_date, track.track_release_date),
              track_artist = COALESCE(EXCLUDED.track_artist, track.track_artist),
              track_title = COALESCE(EXCLUDED.track_title, track.track_title),
              track_album = COALESCE(EXCLUDED.track_album, track.track_album)""")

        cur.execute(f"""
        INSERT INTO track_spotify_audio_features (track_id, track_spotify_audio_features)
        SELECT track_id, '{json.dumps(spotify_details)}'
        FROM track
        WHERE track_path='{escaped_file_path}'
        ON CONFLICT ON CONSTRAINT track_spotify_audio_features_track_id_key
        DO UPDATE
          SET track_spotify_audio_features = EXCLUDED.track_spotify_audio_features""")

        cur.execute(f"""
          INSERT INTO track_embedding
          (track_id, track_embedding_vector, track_embedding_type)
          SELECT track_id, '{embeddings.T.mean(1).tolist()}', '{args.model}'
          FROM track
          WHERE track_path='{escaped_file_path}'
          ON CONFLICT ON CONSTRAINT track_embedding_track_id_track_embedding_type_key
          DO UPDATE
            SET track_embedding_vector = EXCLUDED.track_embedding_vector""")

        conn.commit()
        cur.close()
    except (psycopg2.DatabaseError, Exception) as error:
      print(error)
      traceback.print_exc()

  conn.close()
  print("Processing completed successfully")
  exit(0)
