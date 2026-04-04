"""Build a SCORM 1.2 package zip for the storybook.

Usage:
  python3 build_scorm_package.py

Output:
  dist/palmtree-storybook-scorm12.zip
"""

from __future__ import annotations

import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DIST = ROOT / "dist"
PKG_DIR = DIST / "scorm12_package"
ZIP_PATH = DIST / "palmtree-storybook-scorm12.zip"

MANIFEST = """<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<manifest identifier="palm_tree_storybook_scorm12"
          version="1.0"
          xmlns="http://www.imsproject.org/xsd/imscp_rootv1p1p2"
          xmlns:adlcp="http://www.adlnet.org/xsd/adlcp_rootv1p2"
          xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
          xsi:schemaLocation="http://www.imsproject.org/xsd/imscp_rootv1p1p2 imscp_rootv1p1p2.xsd
                              http://www.adlnet.org/xsd/adlcp_rootv1p2 adlcp_rootv1p2.xsd">
  <metadata>
    <schema>ADL SCORM</schema>
    <schemaversion>1.2</schemaversion>
  </metadata>

  <organizations default="org_1">
    <organization identifier="org_1">
      <title>123 Lets Learn English Under the Palm Tree</title>
      <item identifier="item_1" identifierref="res_1" isvisible="true">
        <title>Interactive Storybook</title>
      </item>
    </organization>
  </organizations>

  <resources>
    <resource identifier="res_1" type="webcontent" adlcp:scormtype="sco" href="scorm_launch.html">
      <file href="scorm_launch.html" />
      <file href="index.html" />
      <file href="palmtreeicon.svg" />
      <file href="scorm_api.js" />
    </resource>
  </resources>
</manifest>
"""

LAUNCH_HTML = """<!DOCTYPE html>
<html lang=\"en\">
<head>
  <meta charset=\"UTF-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\" />
  <title>SCORM Launch - Palm Tree Storybook</title>
  <style>
    body { margin: 0; font-family: Arial, sans-serif; background:#0b1220; color:#e2e8f0; }
    .bar { display:flex; gap:.5rem; align-items:center; padding:.6rem .8rem; background:#111827; border-bottom:1px solid #334155; }
    .bar button { border:0; border-radius:999px; padding:.45rem .8rem; font-weight:700; cursor:pointer; }
    #completeBtn { background:#22c55e; color:#052e16; }
    #saveBtn { background:#38bdf8; color:#082f49; }
    iframe { width:100%; height:calc(100vh - 52px); border:0; background:#020617; }
    input { width:70px; border-radius:6px; border:1px solid #475569; padding:.2rem .35rem; }
  </style>
</head>
<body>
  <div class=\"bar\">
    <strong>SCORM Controls:</strong>
    <label>Score <input id=\"scoreInput\" type=\"number\" value=\"100\" min=\"0\" max=\"100\" /></label>
    <button id=\"saveBtn\">Save Score</button>
    <button id=\"completeBtn\">Complete Lesson</button>
    <span id=\"status\"></span>
  </div>

  <iframe src=\"index.html\" title=\"Storybook\"></iframe>

  <script src=\"scorm_api.js\"></script>
  <script>
    const statusEl = document.getElementById('status');
    initScorm();

    document.getElementById('saveBtn').addEventListener('click', () => {
      const score = Number(document.getElementById('scoreInput').value || 0);
      reportScore(score);
      statusEl.textContent = `Saved score ${score}`;
    });

    document.getElementById('completeBtn').addEventListener('click', () => {
      completeLesson();
      statusEl.textContent = 'Lesson marked completed';
    });

    window.addEventListener('beforeunload', () => finishScorm());
  </script>
</body>
</html>
"""

SCORM_API_JS = """function findApi(win) {
  let tries = 0;
  while (win && tries < 10) {
    if (win.API) return { version: '1.2', api: win.API };
    if (win.API_1484_11) return { version: '2004', api: win.API_1484_11 };
    win = win.parent;
    tries++;
  }
  return null;
}

const scormRef = findApi(window);

function initScorm() {
  if (!scormRef) return;
  if (scormRef.version === '1.2') scormRef.api.LMSInitialize('');
  else scormRef.api.Initialize('');
}

function reportScore(score) {
  if (!scormRef) return;
  const s = String(Math.max(0, Math.min(100, Number(score) || 0)));

  if (scormRef.version === '1.2') {
    scormRef.api.LMSSetValue('cmi.core.score.min', '0');
    scormRef.api.LMSSetValue('cmi.core.score.max', '100');
    scormRef.api.LMSSetValue('cmi.core.score.raw', s);
    scormRef.api.LMSSetValue('cmi.core.lesson_status', Number(s) >= 70 ? 'passed' : 'failed');
    scormRef.api.LMSCommit('');
  } else {
    scormRef.api.SetValue('cmi.score.min', '0');
    scormRef.api.SetValue('cmi.score.max', '100');
    scormRef.api.SetValue('cmi.score.raw', s);
    scormRef.api.SetValue('cmi.success_status', Number(s) >= 70 ? 'passed' : 'failed');
    scormRef.api.SetValue('cmi.completion_status', 'incomplete');
    scormRef.api.Commit('');
  }
}

function completeLesson() {
  if (!scormRef) return;
  if (scormRef.version === '1.2') {
    scormRef.api.LMSSetValue('cmi.core.lesson_status', 'completed');
    scormRef.api.LMSCommit('');
  } else {
    scormRef.api.SetValue('cmi.completion_status', 'completed');
    scormRef.api.Commit('');
  }
}

function finishScorm() {
  if (!scormRef) return;
  if (scormRef.version === '1.2') scormRef.api.LMSFinish('');
  else scormRef.api.Terminate('');
}
"""


def write(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def build() -> None:
    DIST.mkdir(exist_ok=True)
    if PKG_DIR.exists():
        shutil.rmtree(PKG_DIR)
    PKG_DIR.mkdir(parents=True)

    # copy core content
    shutil.copy2(ROOT / "index.html", PKG_DIR / "index.html")
    shutil.copy2(ROOT / "palmtreeicon.svg", PKG_DIR / "palmtreeicon.svg")

    # write SCORM assets
    write(PKG_DIR / "imsmanifest.xml", MANIFEST)
    write(PKG_DIR / "scorm_launch.html", LAUNCH_HTML)
    write(PKG_DIR / "scorm_api.js", SCORM_API_JS)

    if ZIP_PATH.exists():
        ZIP_PATH.unlink()

    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as zf:
        for file in PKG_DIR.rglob("*"):
            if file.is_file():
                zf.write(file, file.relative_to(PKG_DIR))

    print(f"Built: {ZIP_PATH}")


if __name__ == "__main__":
    build()
