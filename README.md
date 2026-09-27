# William & Mary Campus Explorer

An offline Python desktop app built with CustomTkinter, a Tkinter canvas, and Pillow. The supplied 2026–2027 campus PDF provides the map and all 170 building records. Original numbered labels supply marker coordinates, including the five map insets.

## Run

Install Python 3.10 or newer with Tk support. Extract this entire folder, open a terminal inside it, then run:

```sh
python -m pip install -r requirements.txt
python app.py
```

On Windows, `py` can replace `python`. The standard python.org Windows installer includes Tk. On Linux, install your distribution's `python3-tk` package if Tk is missing. No API key, PDF reader, or network connection is needed after dependency installation.

## Controls

- Search by building name, map number, or printed grid reference.
- Filter the directory by category; matching locations gain colored dots.
- Select a result or click near its printed number to center and highlight it.
- Hover near a building number to show its name in the status bar.
- Scroll or use + / − to zoom. Pointer zoom keeps the point beneath the cursor fixed.
- Drag to pan. Fit map restores the full overview, including map insets.
- Toggle Location dots to show all results on the map.
- Ctrl+F focuses search. Escape clears the search and category filter.

## Files and customization

- `app.py`: complete UI, search, canvas interaction, and rendering code.
- `assets/campus_map.png`: high resolution map cropped from the supplied PDF.
- `assets/locations.json`: editable building names, categories, grid references, and pixel coordinates in the PNG.
- `requirements.txt`: runtime dependencies.

Coordinates identify printed building labels, not surveyed geographic positions. Insets are separate illustrations and do not share a continuous geographic scale. This app has no route planning or live location service. Source-map construction markings are retained. The map and names belong to their respective owners; this is an unofficial interface based on the user-supplied reference.

## Validation

All 170 directory entries were matched to a numbered map label. Asset bounds, unique IDs, search behavior, pointer-centered zoom, pan, selection, and viewport rendering were checked without a display. Python compilation and dependency imports passed. A live desktop rendering check could not be performed in the build environment; run locally to inspect platform-specific font and DPI behavior.
