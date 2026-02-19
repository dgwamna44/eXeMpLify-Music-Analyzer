@echo off
py -m pip install -r requirements.txt
set SCORE_ANALYZER_API_BASE=
py flask_app.py
