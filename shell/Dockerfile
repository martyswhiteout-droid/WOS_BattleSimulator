# shell/Dockerfile — production shell image (Agent A).
# BUILD FROM THE REPO ROOT (the compose file does this for you):
#   docker build -f shell/Dockerfile -t wos-shell .
# The image carries the untouched prototype (wos_sim/ + prototype/) plus the
# shell wrapper; promote.py snaps a TAGGED prototype into this same layout.

FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /srv/wos

# deps first (layer cache): shell deps + the engine's runtime deps
COPY shell/requirements.txt shell/requirements.txt
RUN pip install --no-cache-dir -r shell/requirements.txt numpy openpyxl

# the untouched prototype artifact + the shell (repo-root layout preserved,
# so shell.app.main's repo-root sys.path logic works unchanged)
COPY wos_sim/ wos_sim/
COPY prototype/ prototype/
COPY shell/ shell/
# F1 (EVAL_ROUND_1.md): shell/app/ocr/extract.py + vision.py resolve the
# ingestion skill's validator + v2 schema at runtime from
# <repo_root>/.claude/skills/wos-battlereport-ingestion/ and hard-fail
# without it — every OCR request (including the OCR_MOCK=1 path, which
# still runs the validator) 500'd in this image before this line existed.
COPY .claude/skills/wos-battlereport-ingestion/ .claude/skills/wos-battlereport-ingestion/

# F28 (EVAL_ROUND_1.md, minor): don't run the app as root.
RUN useradd --no-create-home --shell /usr/sbin/nologin wosshell \
    && chown -R wosshell:wosshell /srv/wos
USER wosshell

EXPOSE 8200

# /srv/wos is the repo root inside the image; uvicorn runs from it.
CMD ["uvicorn", "shell.app.main:app", "--host", "0.0.0.0", "--port", "8200"]
