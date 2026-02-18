Hi, welcome to the eXeMpLify repository! My name is Duroje Gwamna, and I am a composer and an IT professional by trade. 
I've always had an interest in writing for concert band, and have a couple published works through the Randall Standridge Music Company
Turns out there are several resources from varying publishers regarding the music grading system. Each one has its own guidelines, and it's up to the composer to use their best judgment when assigning that grade.

After working with my fellow colleagues who write for the concert band medium, I decided to develop a tool to help with the guesswork and offer some insights based on quantitative data.

Most composers work with a score writing software like Sibelius or Musescore, and have the capability of saving their music as a .musicXML file to share amongst people using different software.

Without further ado...


**What it does**

Given a MusicXML score, eXeMpLify:

1. **Parses** the score into a structured representation.
2. Runs a set of **feature analyzers** (each targets one musical dimension).
3. Produces:
   - an **observed grade** (overall)
   - per-analyzer **confidence / grade signals**
   - optional **measure-level “why” details** (flags, rule violations, outliers)

---


**Screenshots**
1. Click Load XML Score to get started (remember to export the score you want to analyze as a .musicXML file.
2. Once selected, the score will show up in the center. You can adjust the zoom as needed.

<img width="1918" height="1065" alt="Screenshot 2026-02-18 134615" src="https://github.com/user-attachments/assets/8c15e560-3532-4f7e-a0d4-2d080bffdb53" />


3. Select the grade you estimate the piece to be on the top right, then click analyze. You can choose to search through partial grades (like 2.5, 3.5), or if you want detailed analysis based on the grade you select only. 
Each sub-process takes ~ 30 seconds.

<img width="598" height="736" alt="Screenshot 2026-02-18 134631" src="https://github.com/user-attachments/assets/52be572c-58b6-4675-ae06-13c2bd8629af" />

4. Once finished, click OK, and each analyzer's confidence score, which is based on the selected grade, will populate on the left panel. Each icon over the bar will provide a detailed analysis that shows on the right panel.
<img width="473" height="840" alt="Screenshot 2026-02-18 134908" src="https://github.com/user-attachments/assets/b6e7f18e-c386-4ce7-a1d5-fd6cce4579e5" />

5. You'll get a scoring overview as long as there's more than one part analyzed (can't provide scoring analysis on solo music).
<img width="638" height="788" alt="image" src="https://github.com/user-attachments/assets/588f10a2-3d4d-4447-9ee7-a17fe7ad8d6a" />

6. A timeline with measure numbers, tempo, key, and meters will populate at the bottom. Clicking on a measure number will provide highlights that are found across all analyzers (uncommon rhythms, high C found in tuba part, etc)
<img width="1898" height="197" alt="image" src="https://github.com/user-attachments/assets/6023d8bb-fdbe-4f1f-9616-2b0c3895cc7c" />

7. An estimated grade will show on the top right (as long as Target Analysis Only is not selected). You can also choose to save the analysis as a csv/JSON.
<img width="674" height="266" alt="image" src="https://github.com/user-attachments/assets/19f92a4c-3b4f-41e5-97cc-1b4c01c2ce97" />


**Project structure**

High-level layout (main folders/scripts): 2

- `analyzers/` — individual analyzers + shared analyzer utilities
- `app_data/` — constants, canonical mappings, grade buckets, configuration
- `data/` — datasets / tables used by analyzers (publisher-derived or hand-curated)
- `data_processing/` — score parsing + transformation helpers
- `models/` — typed models used across analyzers
- `publisher_sources/` — ingestion/normalization for publisher-specific data
- `utilities/` — reusable helpers
- `html/` — front-end UI assets
- `flask_app.py` — web entrypoint 3
- `run_analysis.py` — CLI/runner entrypoint 4

`analyzers/__init__.py` exposes the analyzer base + at least the articulation confidence entrypoint. 

---

**Installation** If wanting to clone

> **Note:** exact dependencies may vary as the project evolves.

1. Create and activate a virtual environment
2. Install dependencies (example):
   ```bash
   pip install -r requirements.txt
