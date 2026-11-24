"""Google Drive helpers for the inverter dashboard.

Finds spreadsheets in a shared Drive folder, sorts them by modified time
(Drive API when GOOGLE_API_KEY is set, otherwise the public folder view),
and resolves file ids from links or file names.
"""
import os
import re

import pandas as pd
import requests
import streamlit as st

# Seconds to wait for Google before giving up, so the page never hangs
DRIVE_TIMEOUT = 20

# Time zone Drive's public folder view uses for its "last modified" column
DRIVE_VIEW_TZ = "America/Los_Angeles"


def get_drive_file_id_from_string(token):
    if not token:
        return None
    if token.startswith("http"):
        m = re.search(r"/d/([a-zA-Z0-9_-]+)", token)
        if m:
            return m.group(1)
        m = re.search(r"[?&]id=([a-zA-Z0-9_-]+)", token)
        if m:
            return m.group(1)
        return None
    # If the token looks like a real Drive file id
    if re.fullmatch(r"[a-zA-Z0-9_-]{25,}", token):
        return token
    return None


def find_drive_file_id_in_folder_page(folder_url, filename):
    try:
        response = requests.get(folder_url, timeout=DRIVE_TIMEOUT)
        response.raise_for_status()
        html = response.text

        # Look for a file id near the filename in the folder page HTML
        for m in re.finditer(r"/d/([a-zA-Z0-9_-]{25,})", html):
            idx = m.start()
            chunk = html[max(0, idx - 800):idx + 800]
            if filename in chunk:
                return m.group(1)

        # As fallback, look for a query-string style id near the filename
        for m in re.finditer(r"[?&]id=([a-zA-Z0-9_-]{25,})", html):
            idx = m.start()
            chunk = html[max(0, idx - 800):idx + 800]
            if filename in chunk:
                return m.group(1)

        # Another fallback: locate the filename and search nearby for an id-like string.
        for m in re.finditer(re.escape(filename), html):
            idx = m.start()
            chunk = html[max(0, idx - 1200):idx + 1200]
            id_match = re.search(r"/d/([a-zA-Z0-9_-]{25,})", chunk)
            if id_match:
                return id_match.group(1)
            id_match = re.search(r"[?&]id=([a-zA-Z0-9_-]{25,})", chunk)
            if id_match:
                return id_match.group(1)
            id_match = re.search(r'["\']([a-zA-Z0-9_-]{25,})["\']', chunk)
            if id_match:
                return id_match.group(1)
    except Exception:
        pass
    return None


EXCEL_EXTENSIONS = (".xlsx", ".xls")


def get_drive_folder_id(folder_url):
    """Pull the folder id out of a Drive folder link (or accept a bare id)."""
    if not folder_url:
        return None
    folder_url = folder_url.strip()
    m = re.search(r"/folders/([a-zA-Z0-9_-]{10,})", folder_url)
    if m:
        return m.group(1)
    m = re.search(r"[?&]id=([a-zA-Z0-9_-]{10,})", folder_url)
    if m:
        return m.group(1)
    if re.fullmatch(r"[a-zA-Z0-9_-]{10,}", folder_url):
        return folder_url
    return None


def get_google_api_key():
    """API key for the Drive API, from Streamlit secrets or the environment."""
    try:
        key = st.secrets.get("GOOGLE_API_KEY")
        if key:
            return key
    except Exception:
        pass
    return os.environ.get("GOOGLE_API_KEY")


def _filename_number(name):
    """Numeric part of a name like 17840308811634.xlsx, used to break ties."""
    digits = re.sub(r"\D", "", name or "")
    return int(digits) if digits else -1


def _list_drive_files_with_api(folder_id, api_key):
    """Drive API v3: exact modifiedTime for every spreadsheet in a public folder."""
    files = []
    page_token = None
    while True:
        params = {
            "q": f"'{folder_id}' in parents and trashed = false",
            "orderBy": "modifiedTime desc",
            "fields": "nextPageToken, files(id, name, modifiedTime)",
            "pageSize": 1000,
            "supportsAllDrives": "true",
            "includeItemsFromAllDrives": "true",
            "key": api_key,
        }
        if page_token:
            params["pageToken"] = page_token
        resp = requests.get("https://www.googleapis.com/drive/v3/files", params=params, timeout=DRIVE_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        for f in data.get("files", []):
            if f.get("name", "").lower().endswith(EXCEL_EXTENSIONS):
                ts = pd.to_datetime(f.get("modifiedTime"), utc=True, errors="coerce")
                files.append((f["id"], f["name"], None if pd.isna(ts) else ts))
        page_token = data.get("nextPageToken")
        if not page_token:
            break
    return files


def _parse_embedded_modified(text):
    """Turn the embedded folder view's 'last modified' text into a timestamp.

    Drive shows a time (e.g. '1:35 PM') for files changed today, 'Nov 20' for
    this year, and 'Mar 26, 2024' or '3/26/24' for older files. For visitors
    who are not signed in it uses US Pacific time, so the result is in that
    zone (a time-only entry later than 'now' there belongs to yesterday).
    """
    text = (text or "").replace(" ", " ").replace("\xa0", " ").strip()
    if not text:
        return None
    now = pd.Timestamp.now(tz=DRIVE_VIEW_TZ)
    for fmt in ("%I:%M %p", "%H:%M"):
        try:
            t = pd.to_datetime(text, format=fmt)
            ts = now.normalize() + pd.Timedelta(hours=t.hour, minutes=t.minute)
            if ts > now:
                ts -= pd.Timedelta(days=1)
            return ts
        except Exception:
            pass
    for fmt in ("%b %d, %Y", "%d %b %Y", "%m/%d/%y", "%m/%d/%Y", "%Y-%m-%d"):
        try:
            return pd.to_datetime(text, format=fmt).tz_localize(DRIVE_VIEW_TZ)
        except Exception:
            pass
    for fmt in ("%b %d", "%d %b"):
        try:
            t = pd.to_datetime(f"{text} {now.year}", format=f"{fmt} %Y").tz_localize(DRIVE_VIEW_TZ)
            if t > now:
                t = t.replace(year=now.year - 1)
            return t
        except Exception:
            pass
    return None


def _list_drive_files_embedded(folder_id):
    """No-key fallback: the public embedded folder view lists 'last modified'."""
    resp = requests.get(
        "https://drive.google.com/embeddedfolderview",
        params={"id": folder_id},
        timeout=DRIVE_TIMEOUT,
        headers={"Accept-Language": "en-US,en;q=0.9"},
    )
    resp.raise_for_status()
    html = resp.text
    files = []
    for block in re.split(r'<div class="flip-entry"', html)[1:]:
        id_m = re.search(r'id="entry-([a-zA-Z0-9_-]{10,})"', block)
        name_m = re.search(r'class="flip-entry-title">([^<]+)<', block)
        mod_m = re.search(r'class="flip-entry-last-modified"><div>([^<]*)<', block)
        if not id_m or not name_m:
            continue
        name = name_m.group(1).strip()
        if not name.lower().endswith(EXCEL_EXTENSIONS):
            continue
        files.append((id_m.group(1), name, _parse_embedded_modified(mod_m.group(1) if mod_m else "")))
    return files


@st.cache_data(ttl=60, show_spinner=False)
def list_drive_files_by_time(folder_url):
    """All spreadsheets in a Drive folder, newest first.

    Returns (files, method) where files is a list of (id, name, modified) and
    modified may be None when Drive did not give a time. Uses the Drive API when
    a GOOGLE_API_KEY is set, otherwise the public embedded folder view, and
    falls back to the old folder-page scrape. Ties (same minute, or no time)
    are broken by the number in the file name, highest first.
    """
    folder_id = get_drive_folder_id(folder_url)
    files, method = [], None

    if folder_id:
        api_key = get_google_api_key()
        if api_key:
            try:
                files = _list_drive_files_with_api(folder_id, api_key)
                method = "Drive API (modified time)"
            except Exception:
                files = []
        if not files:
            try:
                files = _list_drive_files_embedded(folder_id)
                method = "Drive folder view (modified time)"
            except Exception:
                files = []

    if not files:
        files = [(fid, name, None) for fid, name in find_all_drive_files_in_folder_page(folder_url)]
        method = "folder page (file name order)"

    oldest = pd.Timestamp.min.tz_localize("UTC")

    def sort_key(item):
        ts = item[2]
        if ts is None:
            ts = oldest
        elif ts.tzinfo is None:
            ts = ts.tz_localize("UTC")
        return (ts, _filename_number(item[1]))

    files.sort(key=sort_key, reverse=True)
    return files, method


def format_drive_time(ts):
    """Show a Drive modified time in Pakistan time when it carries a timezone."""
    try:
        if ts.tzinfo is not None and str(ts.tzinfo) == DRIVE_VIEW_TZ and ts == ts.normalize():
            # Folder view gave only a date (no time), so show just the date
            return ts.strftime("%d %b %Y")
        if ts.tzinfo is not None:
            ts = ts.tz_convert("Asia/Karachi")
        return ts.strftime("%d %b %Y %I:%M %p")
    except Exception:
        return str(ts)


def find_latest_drive_file_in_folder_page(folder_url):
    """Newest spreadsheet in the folder by modified time: (id, name)."""
    files, _ = list_drive_files_by_time(folder_url)
    if files:
        return files[0][0], files[0][1]
    return find_first_drive_file_in_folder_page(folder_url)


def find_first_drive_file_in_folder_page(folder_url):
    try:
        response = requests.get(folder_url, timeout=DRIVE_TIMEOUT)
        response.raise_for_status()
        html = response.text

        candidates = []

        # Try common JSON-like file entries with id + title/name
        for m in re.finditer(r'"id":"([a-zA-Z0-9_-]{25,})".*?"title":"([^"]+?\.(?:xlsx|xls))"', html, re.DOTALL):
            candidates.append((m.group(1), m.group(2)))
        for m in re.finditer(r'"id":"([a-zA-Z0-9_-]{25,})".*?"name":"([^"]+?\.(?:xlsx|xls))"', html, re.DOTALL):
            candidates.append((m.group(1), m.group(2)))

        # Try direct Drive link patterns around Excel filename text
        for m in re.finditer(r'/d/([a-zA-Z0-9_-]{25,}).{0,200}?([A-Za-z0-9_\-\.]+?\.(?:xlsx|xls))', html):
            candidates.append((m.group(1), m.group(2)))

        # If no direct metadata found, search for filenames and nearby ids
        for m in re.finditer(r'([A-Za-z0-9_\-\.]+?\.(?:xlsx|xls))', html):
            filename = m.group(1)
            start = max(0, m.start() - 1200)
            end = min(len(html), m.end() + 1200)
            chunk = html[start:end]
            id_match = re.search(r'/d/([a-zA-Z0-9_-]{25,})', chunk)
            if id_match:
                candidates.append((id_match.group(1), filename))

        if not candidates:
            file_ids = re.findall(r'/d/([a-zA-Z0-9_-]{25,})', html)
            if file_ids:
                return file_ids[0], None
            file_ids = re.findall(r'[?&]id=([a-zA-Z0-9_-]{25,})', html)
            if file_ids:
                return file_ids[0], None
            data_ids = re.findall(r'data-id="([a-zA-Z0-9_-]{25,})"', html)
            if data_ids:
                return data_ids[0], None
            return None, None

        seen = set()
        unique = []
        for fid, name in candidates:
            if fid not in seen:
                seen.add(fid)
                unique.append((fid, name))

        # Prefer the first found candidate as the latest file in the folder
        return unique[0]
    except Exception:
        return None, None


def find_all_drive_files_in_folder_page(folder_url):
    try:
        resp = requests.get(folder_url, timeout=DRIVE_TIMEOUT)
        resp.raise_for_status()
        html = resp.text
        candidates = []

        # JSON-like entries
        for m in re.finditer(r'"id":"([a-zA-Z0-9_-]{25,})".*?"title":"([^\"]+?\.(?:xlsx|xls))"', html, re.DOTALL):
            candidates.append((m.group(1), m.group(2)))
        for m in re.finditer(r'"id":"([a-zA-Z0-9_-]{25,})".*?"name":"([^\"]+?\.(?:xlsx|xls))"', html, re.DOTALL):
            candidates.append((m.group(1), m.group(2)))

        # direct /d/ links with filenames
        for m in re.finditer(r'/d/([a-zA-Z0-9_-]{25,}).{0,200}?([A-Za-z0-9_\-\.]+?\.(?:xlsx|xls))', html):
            candidates.append((m.group(1), m.group(2)))

        # filenames + nearby ids
        for m in re.finditer(r'([A-Za-z0-9_\-\.]+?\.(?:xlsx|xls))', html):
            filename = m.group(1)
            start = max(0, m.start() - 1200)
            end = min(len(html), m.end() + 1200)
            chunk = html[start:end]
            id_match = re.search(r'/d/([a-zA-Z0-9_-]{25,})', chunk)
            if id_match:
                candidates.append((id_match.group(1), filename))

        # fallback id-only captures
        if not candidates:
            file_ids = re.findall(r'/d/([a-zA-Z0-9_-]{25,})', html)
            for fid in file_ids:
                candidates.append((fid, fid))
            file_ids = re.findall(r'[?&]id=([a-zA-Z0-9_-]{25,})', html)
            for fid in file_ids:
                candidates.append((fid, fid))

        # dedupe preserving order
        seen = set()
        unique = []
        for fid, name in candidates:
            if fid not in seen:
                seen.add(fid)
                unique.append((fid, name))
        return unique
    except Exception:
        return []


def delete_drive_file_with_service_account(sa_path, file_id):
    try:
        from googleapiclient.discovery import build
        from google.oauth2 import service_account
        creds = service_account.Credentials.from_service_account_file(sa_path, scopes=['https://www.googleapis.com/auth/drive'])
        service = build('drive', 'v3', credentials=creds, cache_discovery=False)
        service.files().delete(fileId=file_id).execute()
        return True, None
    except Exception as e:
        return False, str(e)
