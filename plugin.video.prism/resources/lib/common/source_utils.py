"""
Module for common utilities that may be used when working with source items
"""
from __future__ import annotations

import contextlib
import re
import string
from typing import Iterable, Iterator, List, Optional, Set, Tuple

from resources.lib.modules.globals import g

BROWSER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/42.0.2311.135 Safari/537."
    "36 Edge/12.246",
    "Mozilla/5.0 (X11; CrOS x86_64 8172.45.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/51.0.2704.64 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_2) AppleWebKit/601.3.9 (KHTML, like Gecko) "
    "Version/9.0.2 Safari/601.3.9"
    "Safari/537.36",
    "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/47.0.2526.111 Safari/537.36",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:15.0) Gecko/20100101 Firefox/15.0.1",
]

exclusions = ["soundtrack", "gesproken"]
_APOSTROPHE_SUBS = re.compile(r"\\'s|'s|&#039;s| 039 s")
_SEPARATORS = re.compile(r'[:|/,!?()"[\]\-\\_.{}]|(?<![:|/,!?()"[\]\-\\_.{}\s]dd)\+')
_WHITESPACE = re.compile(r'\s+')
_SINGLE_QUOTE = re.compile(r"['`]")
_AMPERSAND = re.compile(r'&#038;|&amp;|&')
_EPISODE_NUMBERS = re.compile(r'.*((?:s\d+ ?e\d+ )|(?:season ?\d+ ?(?:episode|ep) ?\d+)|(?: \d+ ?x ?\d+ ))')
_ASCII_NON_PRINTABLE = re.compile(fr'[^{re.escape(string.printable)}]')

# New: token and pattern helpers for three-pass episode matching
# Basic stop words for episode-title token extraction (keeps this small but extendable)
_EPISODE_TITLE_STOP_WORDS: Set[str] = {
    "the", "a", "an", "and", "of", "in", "on", "for", "to", "with", "by", "from", "at", "is", "it", "this",
    "that", "episode", "ep", "part", "series", "season", "full", "s", "x"
}

# Comprehensive S#E# token pattern (captures multiple common variants)
_cloud_se_token_re = re.compile(
    r"""
    (?P<full>
        (?:
            # S01E02, S.01.E.02, S-01--E-02 etc.
            (?P<form1>s[\s._\-]*0?(?P<s1>\d{1,3})[\s._\-]*e[\s._\-]*0?(?P<e1>\d{1,4}))
        )
        |
        (?:
            # 1x02, 01x02
            (?P<form2>\b(?P<s2>\d{1,3})[xX][\s._\-]*0?(?P<e2>\d{1,4})\b)
        )
        |
        (?:
            # S1-E02 or S1--E02 variants
            (?P<form3>s[\s._\-]*0?(?P<s3>\d{1,3})[\s._\-]*[-]{1,3}[\s._\-]*e[\s._\-]*0?(?P<e3>\d{1,4}))
        )
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)

# Bare episode detection when season is missing (E480, EP-480, .480, -480)
_cloud_bare_ep_re = re.compile(
    r"""
    (?:
        (?<!\w)
        (?:ep[\s._\-]*0?(?P<ep1>\d{1,4}))
        |
        (?:\b[eE][\s._\-]*0?(?P<ep2>\d{1,4})\b)
        |
        (?:\.(?P<ep3>0?\d{1,4})(?!\d))
        |
        (?:(?<=\b)\-(?P<ep4>\d{1,4})\b)
    )
    """,
    re.VERBOSE,
)

# Malformed declarations, e.g. EP15p, EP15p1080 -> should be rejected unless token override
_malformed_ep_decl_re = re.compile(r'\bep0?(?P<ep>\d{1,4})p\b', re.IGNORECASE)

# Helper regex to find a plausible S# or SE token position quickly
_any_se_token_re = re.compile(r'(s0?\d+[\s._\-]*e0?\d+|\b\d{1,3}[xX]\d{1,3}\b)', re.IGNORECASE)


class CannotGenerateRegexFilterException(Exception):
    """Exception used when there is no valid input for generating the regex filters."""

    pass


def get_quality(release_title):
    """
    Identifies resolution based on release title information
    :param release_title: sources release title
    :return: stringed resolution
    """
    release_title = release_title.lower()

    if any(q in release_title for q in ["720", "72o"]):
        return "720p"
    if any(q in release_title for q in ["1080", "1o80", "108o", "1o8o"]):
        return "1080p"
    if any(q in release_title for q in ["2160", "216o"]):
        return "4K"
    with contextlib.suppress(ValueError, IndexError):
        if not release_title[release_title.index("4k") + 2].isalnum():
            return "4K"
    return "SD"


INFO_STRUCT = {
    "videocodec": {
        "AVC",
        "HEVC",
        "XVID",
        "DIVX",
        "WMV",
        "MP4",
        "MPEG",
        "VP9",
        "AV1",
    },
    "hdrcodec": {
        "DV",
        "HDR",
        "HYBRID",
        "SDR",
    },
    "audiocodec": {
        "AAC",
        "DTS",
        "DTS-HD",
        "DTS-HDHR",
        "DTS-HDMA",
        "DTS-X",
        "ATMOS",
        "TRUEHD",
        "DD+",
        "DD",
        "MP3",
        "WMA",
        "OPUS",
    },
    "audiochannels": {
        "2.0",
        "5.1",
        "7.1",
    },
    "misc": {
        "CAM",
        "HDTV",
        "PDTV",
        "REMUX",
        "HD-RIP",
        "BLURAY",
        "DVDRIP",
        "WEB",
        "HC",
        "SCR",
        "3D",
        "60-FPS",
        "BATCH",
    },
    "audiolang": {
        "MULTI-AUDIO",
        "DUAL-AUDIO",
        "DUB",
        "SUB",
    },
    "subtitlelang": {
        "MULTI-SUB",
    },
}


def info_set_to_dict(info_set):
    """
    Converts an info set to a structured dictionary
    :param info_set: info set built with get_info
    :return: structured dictionary
    """
    return {info_prop: sorted(list(info_set & codecs)) for info_prop, codecs in INFO_STRUCT.items()}


INFO_TYPES = {
    "AVC": ["x264", "x 264", "h264", "h 264", "avc"],
    "HEVC": ["x265", "x 265", "h265", "h 265", "hevc"],
    "XVID": ["xvid"],
    "DIVX": ["divx"],
    "MP4": ["mp4"],
    "WMV": ["wmv"],
    "MPEG": ["mpeg"],
    "VP9": ["vp9"],
    "AV1": ["av1"],
    "REMUX": ["remux", "bdremux"],
    "DV": [" dv ", "dovi", "dolby vision", "dolbyvision"],
    "HDR": [
        " hdr ",
        "hdr10",
        "hdr 10",
        "uhd bluray 2160p",
        "uhd blu ray 2160p",
        "2160p uhd bluray",
        "2160p uhd blu ray",
        "2160p bluray hevc truehd",
        "2160p bluray hevc dts",
        "2160p bluray hevc lpcm",
        "2160p us bluray hevc truehd",
        "2160p us bluray hevc dts",
    ],
    "SDR": [" sdr"],
    "AAC": ["aac"],
    "DTS-HDMA": ["hd ma", "hdma"],
    "DTS-HDHR": ["hd hr", "hdhr", "dts hr", "dtshr"],
    "DTS-X": ["dtsx", " dts x"],
    "ATMOS": ["atmos"],
    "TRUEHD": ["truehd", "true hd"],
    "DD+": ["ddp", "eac3", " e ac3", " e ac 3", "dd+", "digital plus", "digitalplus"],
    "DD": [" dd ", "dd2", "dd5", "dd7", " ac3", " ac 3", "dolby digital", "dolbydigital", "dolby5"],
    "MP3": ["mp3"],
    "WMA": [" wma"],
    "2.0": ["2 0 ", "2 0ch", "2ch"],
    "5.1": ["5 1 ", "5 1ch", "6ch"],
    "7.1": ["7 1 ", "7 1ch", "8ch"],
    "BLURAY": ["bluray", "blu ray", "bdrip", "bd rip", "brrip", "br rip", "bdmux"],
    "WEB": [" web ", "webrip", "webdl", "web rip", "web dl", "webmux", "dlmux"],
    "HD-RIP": [" hdrip", " hd rip"],
    "DVDRIP": ["dvdrip", "dvd rip"],
    "HDTV": ["hdtv"],
    "PDTV": ["pdtv"],
    "CAM": [
        " cam ",
        "camrip",
        "cam rip",
        "hdcam",
        "hd cam",
        " ts ",
        " ts1",
        " ts7",
        "hd ts",
        "hdts",
        "telesync",
        " tc ",
        " tc1",
        " tc7",
        "hd tc",
        "hdtc",
        "telecine",
        "xbet",
        "hcts",
        "hc ts",
        "hctc",
        "hc tc",
        "hqcam",
        "hq cam",
    ],
    "SCR": ["scr ", "screener"],
    "HC": [
        "korsub",
        " kor ",
        " hc ",
        "hcsub",
        "hcts",
        "hctc",
        "hchdrip",
        "hardsub",
        "hard sub",
        "sub hard",
        "hardcode",
        "hard code",
        "vostfr",
        "vo stfr",
    ],
    "3D": [" 3d", " half ou", " half sbs"],
    "60-FPS": [" 60 fps", " 60fps"],
    "BATCH": ["batch", "complete series"],
}


def get_info(release_title):
    """
    Identifies and retrieves a list of information based on release title of source
    :param release_title: Release title of source
    :return: List of info meta
    """
    title = f"{clean_title(release_title)} "
    info = {info_prop for info_prop, string_list in INFO_TYPES.items() if any(i in title for i in string_list)}
    if all(i in info for i in ["SDR", "HDR"]):
        info.remove("HDR")
    elif all(i in title for i in ["2160p", "remux"]) and all(i not in info for i in ["HDR", "SDR"]):
        info.add("HDR")
    elif "DV" in info and "hybrid" in title and all(i not in info for i in ["HDR", "SDR"]):
        info.add("HDR")
    if all(i in info for i in ["HDR", "DV"]) and all(i not in title for i in ["hybrid", " hdr"]):
        info.remove("HDR")
    if all(i in info for i in ["HDR", "DV"]):
        info.add("HYBRID")
    if any(i in info for i in ["HDR", "DV"]) and all(i not in info for i in ["HEVC", "AVC", "AV1", "VP9"]):
        info.add("HEVC")
    if all(i in info for i in ["DD", "DD+"]):
        info.remove("DD")
    elif any(i in title for i in ["dtshd", "dts hd"]) and all(i not in info for i in ["DTS-HDMA", "DTS-HDHR"]):
        info.add("DTS-HD")
    elif " dts" in title and all(i not in info for i in ["DTS-HDMA", "DTS-HDHR", "DTS-X", "DTS-HD"]):
        info.add("DTS")
    if all(i in title for i in ["sub", "forced"]):
        info.add("HC")
    if "opus" in title and "AV1" in info:
        info.add("OPUS")
    # Audio language axis (mutually exclusive, mirrors the dual/dub/sub vocabulary).
    if any(i in title for i in ["multi audio", "multi lang", "multiple audio", "multiple lang"]):
        info.add("MULTI-AUDIO")
    elif "dual audio" in title:
        info.add("DUAL-AUDIO")
    elif any(i in title for i in ["dub", "dubbed"]):
        info.add("DUB")
    else:
        info.add("SUB")
    if any(i in title for i in ["multi sub", "multiple sub"]):
        info.add("MULTI-SUB")
    return info


def strip_non_ascii_and_unprintable(text):
    """
    Stirps non ascii and unprintable characters from string
    :param text: text to clean
    :return: cleaned text
    """
    return _ASCII_NON_PRINTABLE.sub("", text)


def clean_title(title, broken=None):
    """
    Returns a cleaned version of the provided title
    :param title: title to be cleaned
    :param broken: set to 1 to remove apostophes, 2 to replace with spaces
    :return: cleaned title
    """
    title = g.deaccent_string(title)
    title = strip_non_ascii_and_unprintable(title)
    title = title.lower()

    apostrophe_replacement = "s"
    if broken == 1:
        apostrophe_replacement = ""
    elif broken == 2:
        apostrophe_replacement = " s"

    title = _APOSTROPHE_SUBS.sub(apostrophe_replacement, title)

    title = _SINGLE_QUOTE.sub("", title)
    title = _SEPARATORS.sub(" ", title)
    title = _WHITESPACE.sub(" ", title)
    title = _AMPERSAND.sub("and", title)

    return title.strip()


def remove_from_title(title, target, clean=True):
    """
    Strips provided string from given title
    :param title: release title
    :param target: the string to be stripped
    :param clean: if true, performs a title clean
    :return: stripped title
    """
    if not target:
        return title

    title = title.replace(f" {str(target).lower()} ", " ")
    title = title.replace(f".{str(target).lower()}.", " ")
    title = title.replace(f"+{str(target).lower()}+", " ")
    title = title.replace(f"-{str(target).lower()}-", " ")
    if clean:
        title = f"{clean_title(title)} "
    else:
        title += " "

    return re.sub(r"\s+", " ", title)


def remove_country(title, country, clean=True):
    """
    Strips country from title
    :param title: title to strip from
    :param country: country of item
    :param clean: set to True if the title should be cleaned as well
    :return: processed title
    """
    title = title.lower()
    if title is None or country is None:
        return title

    if isinstance(country, (list, set)):
        for c in country:
            title = _remove_country(clean, c.lower(), title)
    else:
        title = _remove_country(clean, country.lower(), title)

    return title


def _remove_country(clean, country, title):
    if country in ["gb", "uk"]:
        title = remove_from_title(title, "gb", clean)
        title = remove_from_title(title, "uk", clean)
    else:
        title = remove_from_title(title, country, clean)
    return title


def _get_regex_pattern(titles, suffixes_list, non_escaped_suffixes=None):
    pattern = r"^(?:"
    for title in titles:
        title = title.strip()
        if len(title) > 0:
            pattern += f"{re.escape(title)} |"
    pattern = f"{pattern[:-1]})+(?:"
    for suffix in suffixes_list:
        suffix = suffix.strip()
        if len(suffix) > 0:
            pattern += f"{re.escape(suffix)}|"
    if non_escaped_suffixes:
        for suffix in non_escaped_suffixes:
            pattern += f"{suffix}|"
    pattern = f"{pattern[:-1]})+"
    return re.compile(pattern)


def check_title_match(title_parts, release_title, simple_info):
    """
    Performs cleaning of title and attempts to do a simple matching of title
    :param title_parts: stringed/listed version of title
    :param release_title: sources release title
    :param simple_info: simplified meta data of item
    :return:
    """
    title = f"{clean_title(' '.join(title_parts))} "

    country = simple_info.get("country", "")
    year = simple_info.get("year", "")
    title = remove_country(title, country)
    title = remove_from_title(title, year)

    return release_title.startswith(title)


def check_episode_number_match(release_title):
    """
    Confirms that the release title contains an season and episode number
    :param release_title: Release title of source
    :return: True if present else False
    """
    return _EPISODE_NUMBERS.match(release_title) is not None


def check_episode_title_match(show_titles, release_title, simple_info):
    """
    Simplified loose title matching for episode items
    :param show_titles: tv show titles
    :param release_title: release title of source
    :param simple_info: simplified meta data
    :return: True if match found else False
    """
    release_title = clean_title(release_title)
    if simple_info.get("episode_title", None) is not None:
        episode_title = clean_title(simple_info["episode_title"])
        if len(episode_title.split(" ")) >= 3 and episode_title in release_title:
            for title in show_titles:
                if release_title.startswith(clean_title(title)):
                    return True
    return False


def build_cloud_match_title(item: dict) -> str:
    """Combine cloud folder/path/filename for matching (TorBox, Offcloud, etc.)."""
    if not isinstance(item, dict):
        return ""
    parts: list[str] = []
    for key in ("folder_name", "name", "path", "release_title", "short_name"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            parts.append(value.strip())
    return clean_title(" ".join(parts))


def _show_titles_from_simple_info(simple_info: dict) -> list[str]:
    titles = [simple_info.get("show_title") or ""]
    titles.extend(simple_info.get("show_aliases") or [])
    return [title for title in titles if title]


def _release_contains_show_title(release_title: str, simple_info: dict) -> bool:
    for title in _show_titles_from_simple_info(simple_info):
        for candidate in (
            clean_title_with_simple_info(title, simple_info),
            clean_title(title),
        ):
            if candidate and candidate in release_title:
                return True
    return False


def folder_title_queries(simple_info: dict) -> List[str]:
    """
    Generate cleaned title + aliases to be used for folder matching.
    Returned values are cleaned (normalized) strings suitable for substring matching.
    """
    queries: List[str] = []
    for title in _show_titles_from_simple_info(simple_info):
        cleaned = clean_title_with_simple_info(title, simple_info)
        if cleaned:
            queries.append(cleaned)
    return queries


def folder_name_matches(folder_name: str, simple_info: dict) -> bool:
    """
    Substring match cleaned folder name against show title queries.
    Returns True when any cleaned show title / alias appears in the folder name.
    """
    if not folder_name or not simple_info:
        return False
    folder_clean = clean_title(folder_name)
    for q in folder_title_queries(simple_info):
        if q and q in folder_clean:
            return True
    return False


def episode_title_keep_tokens(episode_title: str) -> Set[str]:
    """
    Extract distinctive episode-title words:
    - tokens length >= 3
    - exclude common stopwords
    - return lowercase tokens
    """
    if not episode_title:
        return set()
    cleaned = clean_title(episode_title)
    tokens = [t for t in cleaned.split() if len(t) >= 3 and t not in _EPISODE_TITLE_STOP_WORDS]
    return set(tokens)


def _filename_tokens(path: str) -> List[str]:
    """
    Split a filename/path into normalized tokens using clean_title and whitespace split.
    """
    if not path:
        return []
    # We want to keep tokenization consistent with clean_title
    cleaned = clean_title(path)
    return [t for t in cleaned.split() if t]


def episode_title_in_release(episode_title: str, filename: str) -> bool:
    """
    Check if episode-title tokens appear in filename. Uses conservative matching:
    - requires at least one distinctive token (>=3 chars) to appear
    - for short titles with many tokens, requires at least two tokens
    """
    if not episode_title or not filename:
        return False
    title_tokens = episode_title_keep_tokens(episode_title)
    if not title_tokens:
        return False
    file_tokens = set(_filename_tokens(filename))
    # If title has many tokens, require 2 matches; otherwise 1
    required = 2 if len(title_tokens) >= 3 else 1
    matches = sum(1 for t in title_tokens if t in file_tokens)
    return matches >= required


def _prefix_contains_show_title(release_title: str, token_start_index: int, simple_info: dict) -> bool:
    """
    Validate that a show title appears before the S#E# or bare episode placement.
    This is a guard against ambiguous filenames where S#E# refers to something else.
    """
    if token_start_index is None or token_start_index < 0:
        return False
    prefix = release_title[:token_start_index]
    # If any cleaned show title appears in prefix, pass
    for title in _show_titles_from_simple_info(simple_info):
        cleaned_title = clean_title_with_simple_info(title, simple_info)
        if cleaned_title and cleaned_title in prefix:
            return True
    # Fallback: if prefix contains none alphanumeric characters (e.g. release group only), allow
    # but be conservative: require at least something that looks like a title before token
    # If prefix contains a reasonable word (length >=3), assume it might be title and allow.
    words = [w for w in prefix.split() if len(w) >= 3]
    return bool(words)


def protected_placement_guard(release_title: str, simple_info: dict) -> bool:
    """
    Locate first S#E# token / bare episode / episode-title span and validate prefix.
    Returns True if placement is acceptable (title exists before token or title tokens override).
    """
    if not release_title:
        return False
    r = clean_title(release_title)

    # Check episode-title tokens first: if they appear anywhere, override placement concerns.
    episode_title = simple_info.get("episode_title")
    if episode_title and episode_title_in_release(episode_title, r):
        return True

    # Find first S#E# token
    m = _cloud_se_token_re.search(r)
    if m:
        start = m.start()
        return _prefix_contains_show_title(r, start, simple_info)

    # If no S#E# token found, look for bare episode
    m2 = _cloud_bare_ep_re.search(r)
    if m2:
        start = m2.start()
        return _prefix_contains_show_title(r, start, simple_info)

    # Nothing to validate, conservatively allow
    return True


def iter_season_episode_tokens(filename: str) -> Iterator[Tuple[int, int]]:
    """
    Yield (season, episode) pairs found in the filename using the comprehensive S/E token regex.
    Returns integer pairs. Skips obviously malformed captures.
    """
    if not filename:
        return
    s = clean_title(filename)
    for m in _cloud_se_token_re.finditer(s):
        # Determine which groups matched
        season = episode = None
        if m.group("s1") and m.group("e1"):
            season = m.group("s1")
            episode = m.group("e1")
        elif m.group("s2") and m.group("e2"):
            season = m.group("s2")
            episode = m.group("e2")
        elif m.group("s3") and m.group("e3"):
            season = m.group("s3")
            episode = m.group("e3")
        if season is None or episode is None:
            continue
        try:
            yield (int(season), int(episode))
        except ValueError:
            continue


def iter_bare_episode_numbers(filename: str) -> Iterator[int]:
    """
    Yield bare episode candidates (integers) when no explicit season token is found.
    These are heuristics and should be used as fallback.
    """
    if not filename:
        return
    s = clean_title(filename)
    for m in _cloud_bare_ep_re.finditer(s):
        for gname in ("ep1", "ep2", "ep3", "ep4"):
            if gname in m.groupdict() and m.group(gname):
                try:
                    num = int(m.group(gname))
                    # Avoid treating years (>=1900 & <=2100) as episode numbers
                    if 1900 <= num <= 2100:
                        continue
                    yield num
                except ValueError:
                    continue


def cloud_episode_matches(release_title: str, simple_info: dict) -> bool:
    """
    Match requested episode against file tokens (S#E#, bare episode, episode-title tokens).
    Follows the priority rules:
      1) Episode-title tokens override mismatches (highest)
      2) Exact S#E# token match with protected placement
      3) Bare episode match with protected placement (lower confidence)
      4) Absolute number fallback if provided in simple_info
    Also rejects malformed declarations like EP15p unless episode-title tokens override.
    """
    if not release_title or not simple_info:
        return False

    r = clean_title(release_title)
    requested_season = simple_info.get("season_number") or simple_info.get("season") or ""
    requested_episode = simple_info.get("episode_number") or simple_info.get("episode") or ""
    absolute_number = simple_info.get("absolute_number")

    try:
        req_season = int(str(requested_season)) if requested_season not in (None, "") else None
    except (ValueError, TypeError):
        req_season = None
    try:
        req_episode = int(str(requested_episode)) if requested_episode not in (None, "") else None
    except (ValueError, TypeError):
        req_episode = None

    # Malformed declarations present? reject unless episode-title tokens override.
    if _malformed_ep_decl_re.search(r):
        episode_title = simple_info.get("episode_title")
        if not (episode_title and episode_title_in_release(episode_title, r)):
            return False

    # Token override: if episode title tokens appear, accept immediately
    episode_title = simple_info.get("episode_title")
    if episode_title and episode_title_in_release(episode_title, r):
        return True

    # 1) Try explicit S#E# tokens
    for s, e in iter_season_episode_tokens(r):
        if req_season is not None and req_episode is not None:
            if s == req_season and e == req_episode:
                # ensure show title/prefix is valid
                if _prefix_contains_show_title(r, r.find(str(s)), simple_info):
                    return True
                # allow if protected_placement_guard passes
                if protected_placement_guard(r, simple_info):
                    return True
        else:
            # If no requested season/episode provided but absolute_number is provided,
            # attempt to map using absolute_number; otherwise, accept this if show title present
            if absolute_number not in (None, ""):
                # cannot easily map season/episode to absolute here; skip
                pass
            else:
                # If only a single SE occurrence and show title appears before it, accept
                if _prefix_contains_show_title(r, m.start() if (m := _cloud_se_token_re.search(r)) else 0, simple_info):
                    return True

    # 2) Bare episode numbers fallback
    for num in iter_bare_episode_numbers(r):
        if req_episode is not None and req_episode == num and protected_placement_guard(r, simple_info):
            return True
        if absolute_number not in (None, ""):
            try:
                abs_req = int(str(absolute_number))
                if abs_req == num and protected_placement_guard(r, simple_info):
                    return True
            except (ValueError, TypeError):
                pass

    # 3) Absolute number in filename (padded variants)
    if absolute_number not in (None, ""):
        abs_num = str(absolute_number).lstrip("0") or "0"
        padded = str(absolute_number).zfill(3)
        haystack = f" {r} "
        for needle in (
            f" {padded} ",
            f" {abs_num} ",
            f"-{padded}-",
            f"-{abs_num}-",
            f" e{abs_num} ",
            f" ep{abs_num} ",
            f" episode {abs_num} ",
        ):
            if needle in haystack and protected_placement_guard(r, simple_info):
                return True

    return False


def cloud_loose_episode_match(release_title: str, simple_info: dict) -> bool:
    """Loose episode matching for cloud files when release-group prefixes break anchored regex."""
    release_title = clean_title(release_title)
    if not _release_contains_show_title(release_title, simple_info):
        return False

    season = str(simple_info.get("season_number") or "")
    episode = str(simple_info.get("episode_number") or "")
    if not season or not episode:
        return False

    compact = release_title.replace(" ", "")
    season_fill = season.zfill(2)
    episode_fill = episode.zfill(2)
    for needle in (
        f"s{season_fill}e{episode_fill}",
        f"s{season}e{episode}",
        f"s0{season}e0{episode}",
        f"{season}x{episode}",
        f"{season}x{episode_fill}",
        f"{season_fill}x{episode_fill}",
    ):
        if needle in compact:
            return True

    for pattern in (
        f"season {season} episode {episode}",
        f"season {season_fill} episode {episode_fill}",
        f"season {season} ep {episode}",
        f"season {season_fill} ep {episode_fill}",
    ):
        if pattern in release_title:
            return True

    absolute_number = simple_info.get("absolute_number")
    if absolute_number not in (None, ""):
        abs_num = str(absolute_number).lstrip("0") or "0"
        padded = str(absolute_number).zfill(3)
        haystack = f" {release_title} "
        for needle in (
            f" {padded} ",
            f" {abs_num} ",
            f"-{padded}-",
            f"-{abs_num}-",
            f" e{abs_num} ",
            f" ep{abs_num} ",
            f" episode {abs_num} ",
        ):
            if needle in haystack:
                return True

    # New: token-based override and protected placement guard integration
    # If episode title tokens present, allow match (override)
    episode_title = simple_info.get("episode_title")
    if episode_title and episode_title_in_release(episode_title, release_title):
        return True

    # If explicit S/E tokens exist and protected placement guard passes, accept
    if _cloud_se_token_re.search(release_title) and protected_placement_guard(release_title, simple_info):
        for s, e in iter_season_episode_tokens(release_title):
            if int(s) == int(season) and int(e) == int(episode):
                return True

    # Bare episode fallback
    if any(int(n) == int(episode) for n in iter_bare_episode_numbers(release_title)):
        if protected_placement_guard(release_title, simple_info):
            return True

    return check_episode_title_match(
        [clean_title_with_simple_info(title, simple_info) for title in _show_titles_from_simple_info(simple_info)],
        release_title,
        simple_info,
    )


def cloud_episode_item_matches(
    release_title: str,
    *,
    episode_regex,
    season_regex,
    simple_info: dict,
) -> bool:
    """Return True when a cloud file path matches the requested episode."""
    release_title = clean_title(release_title)
    # Legacy regex check still has high priority
    if episode_regex(release_title) or season_regex(release_title):
        # ensure placement guard passes
        if protected_placement_guard(release_title, simple_info):
            return True

    # Token and title-based matching
    if cloud_episode_matches(release_title, simple_info):
        return True

    # Loose match if everything else failed
    return cloud_loose_episode_match(release_title, simple_info)


def filter_movie_title(org_release_title, release_title, movie_title, simple_info):
    """
    More complex matching of titles for movie items
    :param org_release_title: Original release title of source
    :param release_title: Sources release title
    :param movie_title: Title of Movie
    :param simple_info: Simplified meta data
    :return: True if match found, else False
    """
    year = simple_info.get("year")
    if not year:
        return False
    if org_release_title is not None and year not in org_release_title:
        return False

    title = clean_title(movie_title)
    release_title = clean_title(release_title)

    if "season" in release_title and "season" not in title:
        return False
    if check_episode_number_match(release_title):
        return False

    title_broken_1 = clean_title(movie_title, broken=1)
    title_broken_2 = clean_title(movie_title, broken=2)

    return (
        check_title_match([title], release_title, simple_info)
        or check_title_match([title_broken_1], release_title, simple_info)
        or check_title_match([title_broken_2], release_title, simple_info)
    )


def clean_title_with_simple_info(title, simple_info):
    """
    Cleaning of title and stripping of some known meta data
    :param title: identified title
    :param simple_info: simplified metadata
    :return: cleaned title
    """
    title = f"{clean_title(title)} "
    country = simple_info.get("country", "")
    title = remove_country(title, country)
    year = simple_info.get("year", "")
    title = remove_from_title(title, year)
    title = _WHITESPACE.sub(" ", title)
    return title.rstrip()


def get_filter_single_episode_fn(simple_info):
    """
    Constructs and returns a method to match episode titles
    :param simple_info: simplified metadata
    :return: method that can be used to match titles
    """
    try:
        show_title, season, episode, alias_list = (
            simple_info["show_title"],
            simple_info["season_number"],
            simple_info["episode_number"],
            simple_info["show_aliases"],
        )
    except KeyError:
        raise CannotGenerateRegexFilterException("simple_info must contain (show_title, season_number, episode_number)")

    titles = list(alias_list)
    titles.insert(0, show_title)

    clean_titles = []
    for title in titles:
        clean_titles.append(re.escape(clean_title_with_simple_info(title, simple_info)))

    pattern = r"^(?:{titles})+ ?(?:{year})? ?(?:s0?{ss}e0?{ep}(?: |e\d\d?)|season\ 0?{ss}\ episode\ 0?{ep})+".format(
        titles=" ?|".join(clean_titles),
        year=re.escape(simple_info["year"]),
        ss=re.escape(season),
        ep=re.escape(episode),
    )
    regex = re.compile(pattern)

    def filter_fn(release_title):
        """
        Method to match release titles with supplied metadata
        :param release_title: source release title
        :return: True if match found, else False
        """
        release_title = clean_title(release_title)
        if regex.match(release_title):
            return True

        return check_episode_title_match(clean_titles, release_title, simple_info)

    return filter_fn


def get_filter_season_pack_fn(simple_info):
    """
    Constructs and returns a method to match season pack titles
    :param simple_info: simplified metadata
    :return: method that can be used to match titles
    """
    show_title, season, alias_list = (
        simple_info["show_title"],
        simple_info["season_number"],
        simple_info["show_aliases"],
    )

    titles = list(alias_list)
    titles.insert(0, show_title)

    season_fill = season.zfill(2)
    season_check = f"s{season}"
    season_fill_check = f"s%{season_fill}"
    season_full_check = f"season {season}"
    season_full_fill_check = f"season {season_fill}"

    clean_titles = []
    for title in titles:
        clean_titles.append(clean_title_with_simple_info(title, simple_info))

    suffixes = [
        season_check,
        season_fill_check,
        season_full_check,
        season_full_fill_check,
    ]
    regex_pattern = _get_regex_pattern(clean_titles, suffixes)

    def filter_fn(release_title):
        """
        Method to match release titles with supplied metadata
        :param release_title: source release title
        :return: True if match found, else False
        """
        episode_number_match = check_episode_number_match(release_title)
        if episode_number_match:
            return False

        return bool(re.match(regex_pattern, release_title))

    return filter_fn


def get_filter_show_pack_fn(simple_info):
    """
    Constructs and returns a method to match show pack titles
    :param simple_info: simplified metadata
    :return: method that can be used to match titles
    """
    show_title, season, alias_list, no_seasons, country, year = (
        simple_info["show_title"],
        simple_info["season_number"],
        simple_info["show_aliases"],
        simple_info["no_seasons"],
        simple_info["country"],
        simple_info["year"],
    )

    titles = list(alias_list)
    titles.insert(0, show_title)
    for idx, title in enumerate(titles):
        titles[idx] = clean_title_with_simple_info(title, simple_info)

    all_season_ranges = []
    all_seasons = "1 "
    season_count = 2
    while season_count <= int(no_seasons):
        all_season_ranges.append(f"{all_seasons}and {season_count}")
        all_seasons += f"{season_count} "
        all_season_ranges.append(all_seasons)
        season_count += 1

    all_season_ranges = [x for x in all_season_ranges if season in x]

    def get_pack_names(release_title):
        """
        Method to match release titles with supplied metadata
        :param release_title: source release title
        :return: True if match found, else False
        """
        no_seasons_fill = no_seasons.zfill(2)
        no_seasons_minus_one = str(int(no_seasons) - 1)
        no_seasons_minus_one_fill = no_seasons_minus_one.zfill(2)

        results = [
            f'all {no_seasons} seasons',
            f'all {no_seasons_fill} seasons',
            f'all {no_seasons_minus_one} seasons',
            f'all {no_seasons_minus_one_fill} seasons',
            f"all of serie {no_seasons} seasons",
            f"all of serie {no_seasons_fill} seasons",
            f"all of serie {no_seasons_minus_one} seasons",
            f"all of serie {no_seasons_minus_one_fill} seasons",
            f"all torrent of serie {no_seasons} seasons",
            f"all torrent of serie {no_seasons_fill} seasons",
            f"all torrent of serie {no_seasons_minus_one} seasons",
            f"all torrent of serie {no_seasons_minus_one_fill} seasons",
        ]

        for season_range in all_season_ranges:
            results.append(f"{season_range}")
            results.append(f"season {season_range}")
            results.append(f"seasons {season_range}")

        if "series" not in release_title:
            results.append("series")

        if 'boxset' not in release_title:
            results.append('boxset')

        if 'collection' not in release_title:
            results.append('collection')

        return results

    def get_pack_names_range(last_season):
        """
        Constructs a list of season range strings for regex
        :param last_season: stringed season number
        :return: list of strings for regex comparison
        """
        last_season_fill = last_season.zfill(2)

        return [
            f"{last_season} seasons",
            f"{last_season_fill} seasons",
            f"season 1 {last_season}",
            f"season 01 {last_season_fill}",
            f"season1 {last_season}",
            f"season01 {last_season_fill}",
            f"season 1 to {last_season}",
            f"season 01 to {last_season_fill}",
            f"season 1 thru {last_season}",
            f"season 01 thru {last_season_fill}",
            f"seasons 1 {last_season}",
            f"seasons 01 {last_season_fill}",
            f"seasons1 {last_season}",
            f"seasons01 {last_season_fill}",
            f"seasons 1 to {last_season}",
            f"seasons 01 to {last_season_fill}",
            f"seasons 1 thru {last_season}",
            f"seasons 01 thru {last_season_fill}",
            f"full season 1 {last_season}",
            f"full season 01 {last_season_fill}",
            f"full season1 {last_season}",
            f"full season01 {last_season_fill}",
            f"full season 1 to {last_season}",
            f"full season 01 to {last_season_fill}",
            f"full season 1 thru {last_season}",
            f"full season 01 thru {last_season_fill}",
            f"full seasons 1 {last_season}",
            f"full seasons 01 {last_season_fill}",
            f"full seasons1 {last_season}",
            f"full seasons01 {last_season_fill}",
            f"full seasons 1 to {last_season}",
            f"full seasons 01 to {last_season_fill}",
            f"full seasons 1 thru {last_season}",
            f"full seasons 01 thru {last_season_fill}",
            f"s1 {last_season}",
            f"s1 s{last_season}",
            f"s01 {last_season_fill}",
            f"s01 s{last_season_fill}",
            f"s1 to {last_season}",
            f"s1 to s{last_season}",
            f"s01 to {last_season_fill}",
            f"s01 to s{last_season_fill}",
            f"s1 thru {last_season}",
            f"s1 thru s{last_season}",
            f"s01 thru {last_season_fill}",
            f"s01 thru s{last_season_fill}",
        ]

    suffixes = get_pack_names(show_title)
    seasons_count = int(season)
    while seasons_count <= int(no_seasons):
        suffixes += get_pack_names_range(str(seasons_count))
        seasons_count += 1

    non_escaped_suffixes = [
        "(?!season)(?<!season)complete",
    ]

    regex_pattern = _get_regex_pattern(titles, suffixes, non_escaped_suffixes=non_escaped_suffixes)

    def filter_fn(release_title):
        """
        Method to match release titles with supplied metadata
        :param release_title: source release title
        :return: True if match found, else False
        """
        episode_number_match = check_episode_number_match(release_title)
        if episode_number_match:
            return False

        return bool(re.match(regex_pattern, release_title))

    return filter_fn
