"""
Module for common utilities that may be used when working with source items
"""
from __future__ import annotations

import contextlib
import re
import string
from typing import Iterable

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

# New patterns for three-pass matching and malformed detection
# Allow season up to 3 digits and episode up to 4 digits
_cloud_se_token_re = re.compile(
    r'(?ix)(?:s0*(\d{1,3})[._\-\s]*e0*(\d{1,4})|(?<!\d)(\d{1,3})\s*[xX]\s*0*(\d{1,4})(?!\d))'
)
_cloud_bare_ep_re = re.compile(r'(?ix)(?:\bep[.\-]?\s*0*(\d{1,4})\b|\be0*(\d{1,4})\b|(?<!\d)(?:[._\-\s])0*(\d{1,4})(?:\b|$))')
_malformed_ep_decl_re = re.compile(r'(?i)\bep0*\d+p\b')  # e.g., EP15p glued 'p' notation

# Small stopword list for episode-title token pruning
_STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "from",
    "that",
    "this",
    "they",
    "their",
    "have",
    "has",
    "was",
    "were",
    "are",
    "but",
    "not",
    "you",
    "your",
    "its",
    "it's",
    "a",
    "an",
    "in",
    "on",
    "at",
    "to",
    "of",
    "is",
    "it",
}

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


def cloud_loose_episode_match(release_title: str, simple_info: dict) -> bool:
    """Loose episode matching for cloud files when release-group prefixes break anchored regex."""
    release_title = clean_title(release_title)
    if not _release_contains_show_title(release_title, simple_info):
        # If show title is not present, still allow match if episode-title tokens match strongly
        if simple_info.get("episode_title") and episode_title_in_release(simple_info["episode_title"], release_title):
            return True
        # otherwise require show title to be present for this loose match
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

    # Episode-title override (loose)
    if simple_info.get("episode_title") and episode_title_in_release(simple_info["episode_title"], release_title):
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

    # If provider supplied anchored regex matches, require protected placement guard (unless episode-title overrides)
    try:
        if episode_regex(release_title) or season_regex(release_title):
            # Episode-title override can accept even if placement guard fails
            if simple_info.get("episode_title") and episode_title_in_release(simple_info["episode_title"], release_title):
                return True
            return protected_placement_guard(release_title, simple_info)
    except Exception:
        # In case provided regex callables misbehave, fallback to token based checks
        pass

    # Token and loose checks
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


def is_file_ext_valid(file_name):
    """
    Checks if the video file type is supported by Kodi
    :param file_name: name/path of file
    :return: True if video file is expected to be supported else False
    """
    return file_name.endswith(g.common_video_extensions)


def _full_meta_episode_regex(args):
    """
    Takes an episode items full meta and returns a regex object to use in title matching
    :param args: Full meta of episode item
    :return: compiled regex object
    """
    episode_info = args["info"]
    show_title = clean_title(episode_info["tvshowtitle"])
    country = episode_info.get("country", "")
    if isinstance(country, (list, set)):
        country = '|'.join(country)
    country = country.lower()
    year = episode_info.get("year", "")
    episode_title = clean_title(episode_info.get("title", ""))
    season = str(episode_info.get("season", ""))
    episode = str(episode_info.get("episode", ""))

    if episode_title == show_title or len(re.findall(r"^\d+$", episode_title)) > 0:
        episode_title = None

    reg_string = (
        r"(?#SHOW TITLE)(?:{show_title})"
        r"? ?"
        r"(?#COUNTRY)(?:{country})"
        r"? ?"
        r"(?#YEAR)(?:{year})"
        r"? ?"
        r"(?:(?:[s[]?)0?"
        r"(?#SEASON){season}"
        r"[x .e]|(?:season 0?"
        r"(?#SEASON){season} "
        r"(?:episode )|(?: ep ?)))(?:\d?\d?e)?0?"
        r"(?#EPISODE){episode}"
        r"(?:e\d\d)?\]? "
    )

    reg_string = reg_string.format(show_title=show_title, country=country, year=year, season=season, episode=episode)

    if episode_title:
        reg_string += f"|{episode_title}"

    reg_string = reg_string.replace("*", ".")

    return re.compile(reg_string)


def get_best_episode_match(dict_key, dictionary_list, item_information):
    """
    Attempts to identify the best matching file/s for a given item and list of source files
    :param dict_key: internal key of dictionary in dictionary list to run checks against
    :param dictionary_list: list of dictionaries containing source title
    :param item_information: full meta of episode object
    :return: dictionaries that best matched requested episode
    """
    regex = _full_meta_episode_regex(item_information)
    files = []

    for i in dictionary_list:
        i.update({"regex_matches": regex.findall(clean_title(i[dict_key].split("/")[-1].replace("&", " ").lower()))})
        files.append(i)
    files = [i for i in files if len(i["regex_matches"]) > 0]

    if not files:
        return None

    files = sorted(files, key=lambda x: len(" ".join(x["regex_matches"])), reverse=True)

    return files[0]


def clear_extras_by_string(args, extra_string, folder_details):
    """
    Strips source files that are identified to contain files related to show/movie extras
    :param args: full metadata of requested playback item
    :param extra_string: string used to identify bad source files
    :param folder_details: normalised list of source files
    :return: cleaned list of folder items
    """
    keys_to_confirm_against = ["title", "tvshowtitle"]
    if int(args["info"].get("season", 1)) == 0:
        return folder_details
    for key in keys_to_confirm_against:
        if extra_string in args["info"].get(key, ""):
            return []

    folder_details = [
        i for i in folder_details if extra_string not in clean_title(i["path"].split("/")[-1].replace("&", " ").lower())
    ]
    folder_details = [
        i
        for i in folder_details
        if not any(True for folder in i["path"].split("/") if extra_string.lower() == folder.lower())
    ]

    return [i for i in folder_details if extra_string not in i["path"]]


def filter_files_for_resolving(folder_details, args):
    """
    Ease of use method to filter common strings with clear_extras_by_string
    :param folder_details: normalised list of source files
    :param args: full meta of requested playback item
    :return: cleaned list of folder items
    """
    folder_details = clear_extras_by_string(args, "extras", folder_details)
    folder_details = clear_extras_by_string(args, "specials", folder_details)
    folder_details = clear_extras_by_string(args, "featurettes", folder_details)
    folder_details = clear_extras_by_string(args, "deleted scenes", folder_details)
    folder_details = clear_extras_by_string(args, "sample", folder_details)
    return folder_details


def de_string_size(size):
    """
    Attempts to take a stringed size eg(1GB) and return a integer size in MB
    :param size: identified size
    :type size: str
    :return: size in MB if string can be converted else None
    :rtype int|None:
    """
    if "GB" in size:
        size = float(size.replace("GB", ""))
        return int(size * 1024)
    if "MB" in size:
        size = int(size.replace("MB", "").replace(" ", "").split(".")[0])
        return size
    if "KB" in size:
        size = float(size.replace("KB", ""))
        return int(size * 0.001)
    if "MiB" in size:
        size = int(size.replace("MiB", "").replace(" ", "").split(".")[0])
        return size
    if "GiB" in size:
        size = float(size.replace("GiB", ""))
        return int(size * 1024)
    if "KiB" in size:
        size = float(size.replace("KiB", ""))
        return int(size * 0.001024)


def get_accepted_resolution_set():
    """
    Fetches set of accepted resolutions per settings
    :return: set of resolutions
    :rtype set
    """
    resolutions = ["4K", "1080p", "720p", "SD"]
    max_res = g.get_int_setting("general.maxResolution")
    min_res = g.get_int_setting("general.minResolution")

    return set(resolutions[max_res : min_res + 1])


# -----------------------------
# New token and pattern helpers
# -----------------------------
def _filename_tokens(text: str) -> list[str]:
    """
    Split filename/path into lowercase alpha-numeric tokens.
    Consistent with other tokenizers in the codebase.
    """
    if text is None:
        return []
    cleaned = clean_title(text)
    return [t for t in re.findall(r"[a-z0-9]+", cleaned)]


def episode_title_keep_tokens(episode_title: str) -> set[str]:
    """
    Extract distinctive episode-title words: lowercased tokens, >=3 chars, drop stopwords.
    Returns a set (deduped) suitable for order-independent matching.
    """
    if not episode_title:
        return set()
    tokens = set(_filename_tokens(episode_title))
    tokens = {t for t in tokens if len(t) >= 3 and t not in _STOPWORDS}
    return tokens


def episode_title_in_release(episode_title: str, release_filename: str) -> bool:
    """
    Check if episode-title tokens appear anywhere in filename/path in any order.
    - For short title (<=2 tokens) require exact presence of all tokens.
    - For longer titles require at least 2 tokens or 50% coverage (whichever is larger).
    """
    if not episode_title or not release_filename:
        return False

    query_tokens = episode_title_keep_tokens(episode_title)
    if not query_tokens:
        return False

    candidate_tokens = set(_filename_tokens(release_filename))

    matched = query_tokens & candidate_tokens
    if not matched:
        return False

    if len(query_tokens) <= 2:
        return matched == query_tokens
    threshold = max(2, int(len(query_tokens) * 0.5))
    return len(matched) >= threshold


def folder_title_queries(simple_info: dict) -> list[str]:
    """
    Generate cleaned title + aliases for folder filtering.
    Returns list of normalized titles to compare against folder names.
    """
    if not isinstance(simple_info, dict):
        return []
    titles = _show_titles_from_simple_info(simple_info)
    cleaned = []
    for t in titles:
        ct = clean_title_with_simple_info(t, simple_info)
        if ct:
            cleaned.append(ct)
    return cleaned


def folder_name_matches(folder_name: str, simple_info: dict) -> bool:
    """
    Substring / token match of cleaned folder name against show title queries.
    Matching is order-independent and tolerant:
      - Accept if cleaned folder contains the cleaned show title substring
      - OR if token intersection >= 2 OR >= 60% coverage
    """
    if not folder_name:
        return False
    if not isinstance(simple_info, dict):
        return True

    folder_clean = clean_title(folder_name)
    queries = folder_title_queries(simple_info)
    if not queries:
        # no show title to compare against: do not block (be permissive)
        return True

    folder_tokens = set(_filename_tokens(folder_clean))
    for q in queries:
        if not q:
            continue
        q_clean = clean_title(q)
        if not q_clean:
            continue
        # substring shortcut
        if q_clean in folder_clean:
            return True
        q_tokens = set(_filename_tokens(q_clean))
        if not q_tokens:
            continue
        matched = q_tokens & folder_tokens
        if len(matched) >= 2:
            return True
        if len(matched) / len(q_tokens) >= 0.6:
            return True
    return False


def _prefix_contains_show_title(candidate: str, simple_info: dict, token_start_index: int) -> bool:
    """
    Returns True if any show title candidate appears in candidate text
    at an index earlier than token_start_index (i.e. before the S/E or bare-EP).
    If no show title is present at all, return False.
    """
    if not candidate or not isinstance(simple_info, dict):
        return False
    candidate_clean = clean_title(candidate)
    earliest_title_index = None
    for title in _show_titles_from_simple_info(simple_info):
        for candidate_variant in (clean_title_with_simple_info(title, simple_info), clean_title(title)):
            if not candidate_variant:
                continue
            idx = candidate_clean.find(candidate_variant)
            if idx >= 0:
                if earliest_title_index is None or idx < earliest_title_index:
                    earliest_title_index = idx
    if earliest_title_index is None:
        return False
    return earliest_title_index < token_start_index


def protected_placement_guard(candidate: str, simple_info: dict) -> bool:
    """
    Locate first S#E token / bare episode / episode-title span and validate that, if a show title exists
    in the filename/folder, it appears before that token. This reduces false positives where numbers
    belong to unrelated content.

    Behaviour:
    - If episode-title tokens are strongly present (episode_title_in_release), returns True (override).
    - If no S/E or bare-EP token found, returns True.
    - If show title is not present in the candidate at all, return True (per current requirement).
    - If show title exists and appears before the first token -> True; if show title appears after token -> False.
    """
    if not candidate or not isinstance(simple_info, dict):
        return True

    cleaned = clean_title(candidate)

    # Episode-title override
    if simple_info.get("episode_title") and episode_title_in_release(simple_info["episode_title"], cleaned):
        return True

    # find first SE token
    se_match = None
    for m in _cloud_se_token_re.finditer(candidate):
        se_match = m
        break
    bare_match = None
    if se_match is None:
        for m in _cloud_bare_ep_re.finditer(candidate):
            bare_match = m
            break

    if se_match is None and bare_match is None:
        # No tokens to validate placement for; be permissive
        return True

    # Determine token index (use start of matched span in cleaned string)
    token_span_index = None
    # To get an index in cleaned, search for the matched text's cleaned variant
    if se_match:
        raw_token = se_match.group(0)
        token_index = clean_title(candidate).find(clean_title(raw_token))
        token_span_index = token_index if token_index >= 0 else None
    elif bare_match:
        raw_token = bare_match.group(0)
        token_index = clean_title(candidate).find(clean_title(raw_token))
        token_span_index = token_index if token_index >= 0 else None

    if token_span_index is None:
        # If we couldn't compute a reliable index, be permissive
        return True

    # If show title present and appears after token -> reject
    if _release_contains_show_title(cleaned, simple_info):
        if not _prefix_contains_show_title(candidate, simple_info, token_span_index):
            return False

    # Otherwise accept
    return True


def iter_season_episode_tokens(text: str) -> Iterable[tuple]:
    """
    Yield (season, episode) pairs found in the provided text using generous SE patterns.
    Season up to 3 digits, episode up to 4 digits.
    """
    if not text:
        return
    for m in _cloud_se_token_re.finditer(text):
        g1, g2, g3, g4 = m.groups() + (None,) * (4 - len(m.groups()))
        if g1 and g2:
            yield g1, g2
        elif g3 and g4:
            yield g3, g4


def iter_bare_episode_numbers(text: str) -> Iterable[str]:
    """
    Yield bare episode candidates found in text (E480, EP480, .480 etc).
    Filters out obvious year matches (1900-2100).
    """
    if not text:
        return
    for m in _cloud_bare_ep_re.finditer(text):
        groups = m.groups() or ()
        for g in groups:
            if not g:
                continue
            try:
                n = int(g)
            except Exception:
                continue
            # filter likely years
            if 1900 <= n <= 2100:
                continue
            yield str(n)


def cloud_episode_matches(release_title: str, simple_info: dict) -> bool:
    """
    Token-based matching to decide if a file likely matches requested episode.
    Matches:
      - episode-title tokens (override)
      - explicit SE tokens (require protected placement unless override)
      - bare episode numbers (require protected placement unless override)
      - absolute numbers (padded variants)
    """
    if not isinstance(simple_info, dict):
        return False

    cleaned = clean_title(release_title)

    # Episode-title override (highest priority)
    if simple_info.get("episode_title") and episode_title_in_release(simple_info["episode_title"], cleaned):
        return True

    # Requested coords
    season_req = simple_info.get("season_number") or simple_info.get("season")
    episode_req = simple_info.get("episode_number") or simple_info.get("episode")
    try:
        season_req_i = int(str(season_req)) if season_req not in (None, "") else None
    except Exception:
        season_req_i = None
    try:
        episode_req_i = int(str(episode_req)) if episode_req not in (None, "") else None
    except Exception:
        episode_req_i = None

    # Explicit S#E# tokens
    if season_req_i is not None and episode_req_i is not None:
        for s, e in iter_season_episode_tokens(release_title):
            try:
                if int(s) == season_req_i and int(e) == episode_req_i:
                    if protected_placement_guard(release_title, simple_info):
                        return True
            except Exception:
                continue

    # Bare episode numbers (fallback)
    if episode_req_i is not None:
        for n in iter_bare_episode_numbers(release_title):
            try:
                if int(n) == episode_req_i:
                    if protected_placement_guard(release_title, simple_info):
                        return True
            except Exception:
                continue

    # Absolute number fallback
    absolute_number = simple_info.get("absolute_number")
    if absolute_number not in (None, ""):
        try:
            abs_req = int(str(absolute_number))
            padded = str(abs_req).zfill(3)
            haystack = f" {cleaned} "
            for needle in (
                f" {padded} ",
                f" {abs_req} ",
                f"-{padded}-",
                f"-{abs_req}-",
                f" e{abs_req} ",
                f" ep{abs_req} ",
                f" episode {abs_req} ",
            ):
                if needle in haystack and protected_placement_guard(release_title, simple_info):
                    return True
        except Exception:
            pass

    return False
