# TransLingo QA Studio

An AI-powered desktop application for validating translated screenshots across multiple translation engines. Built with Python and PySide6.

## Features

- **Multi-engine comparison**: Google Translate, Papago, Samsung Translate, Microsoft Translator, and custom engines
- **16 validation parameters**: OCR accuracy, semantic similarity, layout shift, blur detection, artifact detection, overflow detection, and more
- **Weighted scoring model** (0–100) with configurable weights
- **Side-by-side image viewer** with zoom, pan, overlay, and heatmap modes
- **Reports**: PowerPoint, Excel, CSV, and HTML export
- **SQLite database** for run history and result comparison
- **Dark / Light themes**
- **Parallel processing** for 200+ images

## Supported Language Pairs

| Source | Target |
|--------|--------|
| English | Korean |
| Korean | Hindi |
| Chinese | English |
| Japanese | English |
| Any custom pair | — |

## Installation

### Prerequisites

- Python 3.10+
- pip

### Quick Start

```bash
# Clone / download the project
cd translingo_qa_studio

# Create a virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate     # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Launch the application
python main.py
```

### Generate Sample Data

```bash
python sample_data/generate_samples.py --count 20
```

This creates `sample_data/Original/`, `sample_data/Google/`, `sample_data/Papago/`, `sample_data/Samsung/` with synthetic UI screenshots.

## Input Folder Structure

```
Root Folder/
  Original/
      image001.png
      image002.png
      ...
  Google/
      image001.png
      image002.png
      ...
  Papago/
      image001.png
      ...
  Samsung/
      image001.png
      ...
```

- The `Original/` folder contains source-language screenshots.
- Each engine folder contains the translated screenshots with **identical filenames**.

## Usage

1. **Launch** `python main.py`
2. Go to **Run Validation** in the sidebar.
3. Click **Browse** to select your root folder.
4. Select the source and target languages.
5. Choose which engines to include.
6. Click **▶ Start Validation**.
7. View results in the **Results** tab.
8. Export reports from the **Reports** tab.

## Scoring Model

| Parameter | Default Weight |
|-----------|---------------|
| Semantic Similarity | 25 |
| OCR Accuracy | 15 |
| Character Coverage | 10 |
| Layout Similarity | 10 |
| Font Consistency | 10 |
| Artifact Detection | 10 |
| Background Preservation | 10 |
| Blur Detection | 5 |
| Overflow Detection | 5 |

### Score Bands

| Range | Band |
|-------|------|
| 95–100 | Excellent |
| 85–94 | Good |
| 70–84 | Acceptable |
| < 70 | Needs Review |

## Running Tests

```bash
python -m pytest tests/ -v
# or
python -m unittest discover tests/
```

## Building an Executable

```bash
pip install pyinstaller
pyinstaller translingo.spec
# Output: dist/TransLingoQAStudio/
```

## Architecture

```
translingo_qa_studio/
├── main.py                    # Entry point
├── requirements.txt
├── translingo.spec            # PyInstaller build spec
├── app/
│   ├── ui/
│   │   ├── main_window.py     # Main application window
│   │   ├── sidebar.py         # Navigation sidebar
│   │   ├── dashboard_widget.py
│   │   ├── validation_widget.py
│   │   ├── results_widget.py
│   │   ├── reports_widget.py
│   │   ├── settings_widget.py
│   │   ├── image_viewer.py    # Zoom/pan/overlay/heatmap viewer
│   │   └── charts_widget.py   # Matplotlib charts
│   ├── core/
│   │   ├── ocr_engine.py      # PaddleOCR wrapper
│   │   ├── semantic_validator.py  # SentenceTransformers
│   │   ├── visual_validator.py    # OpenCV / skimage
│   │   ├── scoring_engine.py      # Weighted scoring
│   │   ├── benchmark_engine.py    # Multi-engine orchestration
│   │   └── report_generator.py    # PPTX / Excel / CSV / HTML
│   ├── models/
│   │   └── data_models.py
│   ├── database/
│   │   └── db_manager.py      # SQLite
│   └── resources/
│       └── styles/
│           ├── dark_theme.qss
│           └── light_theme.qss
├── tests/
│   ├── test_scoring.py
│   ├── test_database.py
│   └── test_visual.py
└── sample_data/
    ├── generate_samples.py
    ├── Original/
    ├── Google/
    ├── Papago/
    └── Samsung/
```

## Dependencies

| Library | Purpose |
|---------|---------|
| PySide6 | Desktop UI |
| PaddleOCR | Multilingual OCR |
| sentence-transformers | Semantic similarity |
| OpenCV | Image processing |
| scikit-image | SSIM / structural analysis |
| matplotlib | Charts |
| python-pptx | PowerPoint generation |
| pandas + openpyxl | Excel export |
| Jinja2 | HTML templates |
| loguru | Logging |

## Settings

All settings are persisted in SQLite (`~/.translingo_qa/translingo.db`):

- **Theme**: Dark / Light
- **Scoring weights**: Adjustable per parameter
- **OCR confidence threshold**: 0.1 - 1.0
- **Parallel workers**: 1 - 16
- **Thumbnail size**: 100 - 500 px

## License

MIT License
