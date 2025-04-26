# Track Feature Extractor

Build a feature database from local tracks and perform similarity searches based on audio analysis.

## Third-Party Models and License

This project uses machine learning models developed by [Essentia](https://essentia.upf.edu/models.html#discogs-effnet), licensed under the [CC BY-NC-SA 4.0 license](https://essentia.upf.edu/models/LICENSE).  
Model weights and metadata files are located in the `models` folder.

## Prerequisites

To run the scripts, you need:

- **PostgreSQL** with the **pgvector** extension installed.

You can install them on macOS using [Homebrew](https://brew.sh):

```bash
brew install postgresql pgvector
```

## Setup (MacOS)

Use the provided `setup.command` script to set up the environment. This will:

- Create the track database
- Install Python dependencies

Run the script by double-clicking it in Finder.


## Usage (macOS)

### Analyzing Tracks

Use the `analyse.command` script to recursively process tracks in a folder.

- Double-click `analyse.command` in Finder.
- When prompted, drag and drop a folder into the terminal window and press Enter.

You'll see informational logs as the script processes the tracks.  
Once finished, the terminal will display:

```
[Process completed]
```

### Performing Searches

After analyzing the tracks, start the search interface using `prompt.command` (double-click in Finder).

> ⚠️ **Note:** The current search UI is basic and may feel clunky, but it is functional.

**Basic search:**

- Type `s` followed by a search term (e.g., track title, artist name) and press Enter.
- A list of results will appear.

**Example:**

```
MacBook Pro Speakers any_BPM any_key >1900 >>> s noisia
+-----+------+--------------------------------------------+----------------------------------------------------------+-----------+-------+-------+
|   # |   ID | Artist                                     | Title                                                    | Comment   |   BPM | Key   |
|-----+------+--------------------------------------------+----------------------------------------------------------+-----------+-------+-------|
|   0 |  401 | What So Not                                | Divide & Conquer (Noisia Remix)                          |           |    86 | 4A    |
|   1 |  632 | Noisia                                     | Into Dust (Neonlight Remix)                              |           |   172 | 6A    |
|   2 |  810 | Noisia, Former                             | Pleasure Model (Original Mix)                            |           |   115 | 9A    |
+-----+------+--------------------------------------------+----------------------------------------------------------+-----------+-------+-------+
```

**Selecting a track:**

-  Type `s` followed by the index number of a track to select it for similarity search.

```
MacBook Pro Speakers any_BPM any_key >1900 >>> s 1
Selected track: Noisia - Into Dust (Neonlight Remix)  [172 6A]
+-----+-------+----------------------------+---------------------------------------------+-----------+-------+-------+
|   # |    ID | Artist                     | Title                                       | Comment   |   BPM | Key   |
|-----+-------+----------------------------+---------------------------------------------+-----------+-------+-------|
|   0 |   540 | Joe Ford                   | Tomb Raver (Original Mix)                   |           |    86 | 5A    |
|   1 |  6829 | The Upbeats, Agressor Bunx | Cauldron feat. Agressor Bunx (Original Mix) |           |   174 | 6A    |
+-----+-------+----------------------------+---------------------------------------------+-----------+-------+-------+
```

### Filtering Results

You can refine your search using BPM and key filters.

- **Set BPM filter:** Type `b` followed by the desired BPM.

```
MacBook Pro Speakers any_BPM any_key >1900 >>> b 140
MacBook Pro Speakers 140 any_key >1900 >>> k 4B
MacBook Pro Speakers 140 4B >1900 >>> 
```

- **Set Key filter:** Type `k` followed by the desired key.

```
MacBook Pro Speakers 140 any_key >1900 >>> k 4B
```

The search will return tracks within a small BPM tolerance and compatible keys (based on the Circle of Fifths / Camelot Wheel).

---

## Notes

> ⚠️ **Work in Progress:**  
> This project is under active development and may not always function as expected.

TODO: Add artist and filename to search
