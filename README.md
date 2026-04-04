# ar-project

A single-file HTML5 interactive storybook themed around:
**"123 Lets Learn English Under the Palm Tree"**.

## Features

- Main app is in `index.html` (HTML + CSS + JavaScript).
- Dedicated advanced writing activity page: `write-with-palm.html`.
- Palm tree graphics use `palmtreeicon.svg` beside the two title lines only.
- Refined premium visual style (glass cards, smoother controls, cleaner progress UI).
- Chapter-gate progression: Chapter N+1 stays locked until required Chapter N activities are completed.
- Full multi-skill learning flow:
  - Reading chapters (9 chapters + choices)
  - Listening mode (Listen + Mute + hover-to-listen)
  - Vocabulary challenge
  - Critical thinking reflection
  - Writing practice with word count
  - Drawing & coloring canvas
  - Hotspot listening activity
  - Levels (Bronze/Silver/Gold)
  - Progress bar across all skills
  - Certificate generator
  - Auto remedial plan suggestions

## Run Storybook

```bash
python3 -m http.server 8000
```

Then open:

`http://localhost:8000`

> No external libraries are required for the storybook.

## Build Full SCORM 1.2 Package (ZIP)

To generate a complete SCORM upload package (including `imsmanifest.xml`):

```bash
python3 build_scorm_package.py
```

Output file:

- `dist/palmtree-storybook-scorm12.zip`

Upload this ZIP directly to your LMS (for example Moodle SCORM activity).

## Optional: Speech + Reading Evaluator (Python)

A helper script `evaluate_speech.py` is included for speaking/reading scoring with:
- pause-aware fluency (fewer pauses gets a higher score),
- multiple recordings support,
- SCORM-ready export files.

### Setup

```bash
py -m pip install openai-whisper jiwer librosa soundfile numpy
```

Install FFmpeg (Windows):

```bash
winget install Gyan.FFmpeg
```

### Usage

Single recording:

```bash
py evaluate_speech.py
```

Multiple recordings (different voices/attempts):

```bash
py evaluate_speech.py student1.wav student2.wav student3.wav
```

### SCORM output

After each run, two files are created:
- `scorm_result.json` (score payload)
- `scorm_result.js` (ready snippet for SCORM 1.2/2004 API calls)


## Content Handoff Template

To send your custom content in manageable chunks, use this JSON shape per chapter:

```json
{
  "chapter": 1,
  "title": "Chapter 1 title",
  "text": "Main chapter text",
  "question": "Main question",
  "choices": ["Choice A", "Choice B"],
  "results": ["Result A", "Result B"],
  "vocabulary": ["word 1", "word 2"],
  "critical_prompt": "One deep thinking prompt",
  "writing_prompt": "One writing task",
  "hotspots": [
    "fact for hotspot 1",
    "fact for hotspot 2",
    "fact for hotspot 3"
  ]
}
```

You can send one chapter at a time (recommended), and each chapter will be wired to the lock/unlock learning sequence.
