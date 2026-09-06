# Import Thread lock workaround
# noinspection PyUnresolvedReferences
from __future__ import annotations

import contextlib
import datetime
import html
import json
import os
import re
import traceback
import unicodedata
from functools import cached_property
from urllib import parse
from xml.etree import ElementTree

import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin
import xbmcvfs
from unidecode import unidecode

from resources.lib.modules.settings_cache import PersistedSettingsCache
from resources.lib.modules.settings_cache import RuntimeSettingsCache
from resources.lib.third_party import pytz

viewTypes = [
    ("Default", 50),
    ("Poster", 51),
    ("Icon Wall", 52),
    ("Shift", 53),
    ("Info Wall", 54),
    ("Wide List", 55),
    ("Wall", 500),
    ("Banner", 501),
    ("Fanart", 502),
]

colorChart = [
    "black",
    "white",
    "whitesmoke",
    "gainsboro",
    "lightgray",
    "silver",
    "darkgray",
    "gray",
    "dimgray",
    "snow",
    "floralwhite",
    "azure",
    "aliveblue",
    "lightsaltegray",
    "lightsteelblue",
    "powderblue",
    "lightblue",
    "skyblue",
    "lightskyblue",
    "deepskyblue",
    "dodgerblue",
    "royalblue",
    "blue",
    "mediumblue",
    "midnightblue",
    "navy",
    "darkblue",
    "cornflowerblue",
    "slateblue",
    "slategray",
    "yellowgreen",
    "springgreen",
    "seagreen",
    "steelblue",
    "teal",
    "fuchsia",
    "deeppink",
    "darkmagenta",
    "blueviolet",
    "darkviolet",
    "darkorchid",
    "darkslateblue",
    "darkslategray",
    "indigo",
    "cadetblue",
    "darkcyan",
    "darkturquoise",
    "turquoise",
    "cyan",
    "paleturquoise",
    "lightcyan",
    "mintcream",
    "honeydew",
    "aqua",
    "aquamarine",
    "chartreuse",
    "greenyellow",
    "palegreen",
    "lawngreen",
    "lightgreen",
    "lime",
    "mediumspringgreen",
    "mediumturquoise",
    "lightseagreen",
    "mediumaquamarine",
    "mediumseagreen",
    "limegreen",
    "darkseagreen",
    "forestgreen",
    "green",
    "darkgreen",
    "darkolivegreen",
    "olive",
    "olivedab",
    "darkkhaki",
    "khaki",
    "gold",
    "goldenrod",
    "lightyellow",
    "lightgoldenrodyellow",
    "lemonchiffon",
    "yellow",
    "seashell",
    "lavenderblush",
    "lavender",
    "lightcoral",
    "indianred",
    "darksalmon",
    "lightsalmon",
    "pink",
    "lightpink",
    "hotpink",
    "magenta",
    "plum",
    "violet",
    "orchid",
    "palevioletred",
    "mediumvioletred",
    "purple",
    "marron",
    "mediumorchid",
    "mediumpurple",
    "mediumslateblue",
    "thistle",
    "linen",
    "mistyrose",
    "palegoldenrod",
    "oldlace",
    "papayawhip",
    "moccasin",
    "navajowhite",
    "peachpuff",
    "sandybrown",
    "peru",
    "chocolate",
    "orange",
    "darkorange",
    "tomato",
    "orangered",
    "red",
    "crimson",
    "salmon",
    "coral",
    "firebrick",
    "brown",
    "darkred",
    "tan",
    "rosybrown",
    "sienna",
    "saddlebrown",
]

info_labels = {
    "genre",
    "country",
    "year",
    "episode",
    "season",
    "sortepisode",
    "sortseason",
    "episodeguide",
    "showlink",
    "top250",
    "setid",
    "tracknumber",
    "rating",
    "userrating",
    "watched",
    "playcount",
    "overlay",
    "castandrole",
    "director",
    "mpaa",
    "plot",
    "plotoutline",
    "title",
    "originaltitle",
    "sorttitle",
    "duration",
    "studio",
    "tagline",
    "writer",
    "tvshowtitle",
    "premiered",
    "status",
    "set",
    "setoverview",
    "tag",
    "imdbnumber",
    "code",
    "aired",
    "credits",
    "lastplayed",
    "album",
    "artist",
    "votes",
    "path",
    "trailer",
    "dateadded",
    "mediatype",
    "dbid",
}

info_dates = {
    "premiered",
    "aired",
    "lastplayed",
    "dateadded",
}


def normalize_cast_to_actors(cast_list):
    """
    Convert cast dictionaries to xbmc.Actor objects for InfoTagVideo.setCast().
    
    :param cast_list: List of cast dictionaries with 'name', 'role', 'order', 'thumbnail' keys
    :return: List of xbmc.Actor objects
    """
    if not cast_list or not isinstance(cast_list, (list, set)):
        return []
    
    actors = []
    for idx, cast_member in enumerate(cast_list):
        if not isinstance(cast_member, dict):
            continue
        name = cast_member.get("name", "")
        if not name:
            continue
        role = cast_member.get("role", cast_member.get("character", ""))
        order = cast_member.get("order", idx)
        thumbnail = cast_member.get("thumbnail") or cast_member.get("thumb") or cast_member.get("profile_path") or ""
        try:
            actors.append(xbmc.Actor(name, role, order, thumbnail or ""))
        except Exception:
            # Fallback if xbmc.Actor fails
            pass
    return actors


def build_unique_ids_for_info(info):
    """Map Prism info fields to Kodi InfoTagVideo unique ID keys."""
    if not isinstance(info, dict):
        return {}

    media_type = info.get("mediatype")
    id_keys = {
        "tmdb_id": "tmdb",
        "imdb_id": "imdb",
        "tvdb_id": "tvdb",
        "simkl_id": "simkl",
        "mal_id": "mal",
    }
    unique_ids = {}
    for id_key, unique_id_key in id_keys.items():
        lookup = f"tvshow.{id_key}" if media_type in ("episode", "season") else id_key
        value = info.get(lookup) or info.get(id_key)
        if value:
            unique_ids[unique_id_key] = str(value)
    return unique_ids


def set_video_info_tag(item, info, cast=None, unique_ids=None):
    """
    Set video metadata using InfoTagVideo API (Kodi 21+).
    
    :param item: xbmcgui.ListItem
    :param info: Dictionary of info labels
    :param cast: List of cast dictionaries (optional)
    :param unique_ids: Dictionary of unique IDs (optional)
    """
    info_tag = item.getVideoInfoTag()
    
    # Basic info
    if info.get("title"):
        info_tag.setTitle(str(info["title"]))
    if info.get("originaltitle"):
        info_tag.setOriginalTitle(str(info["originaltitle"]))
    if info.get("sorttitle"):
        info_tag.setSortTitle(str(info["sorttitle"]))
    if info.get("plot"):
        info_tag.setPlot(str(info["plot"]))
    elif info.get("overview"):
        info_tag.setPlot(str(info["overview"]))
    if info.get("plotoutline"):
        info_tag.setPlotOutline(str(info["plotoutline"]))
    if info.get("tagline"):
        info_tag.setTagLine(str(info["tagline"]))
    if info.get("mediatype"):
        info_tag.setMediaType(str(info["mediatype"]))
    
    # Numeric fields
    if info.get("year"):
        try:
            info_tag.setYear(int(info["year"]))
        except (ValueError, TypeError):
            pass
    if info.get("episode") is not None:
        try:
            info_tag.setEpisode(int(info["episode"]))
        except (ValueError, TypeError):
            pass
    if info.get("season") is not None:
        try:
            info_tag.setSeason(int(info["season"]))
        except (ValueError, TypeError):
            pass
    if info.get("sortepisode") is not None:
        try:
            info_tag.setSortEpisode(int(info["sortepisode"]))
        except (ValueError, TypeError):
            pass
    if info.get("sortseason") is not None:
        try:
            info_tag.setSortSeason(int(info["sortseason"]))
        except (ValueError, TypeError):
            pass
    if info.get("duration"):
        try:
            info_tag.setDuration(int(info["duration"]))
        except (ValueError, TypeError):
            pass
    elif info.get("runtime"):
        try:
            info_tag.setDuration(int(float(info["runtime"]) * 60))
        except (ValueError, TypeError):
            pass
    if info.get("playcount") is not None:
        try:
            info_tag.setPlaycount(int(info["playcount"]))
        except (ValueError, TypeError):
            pass
    if info.get("userrating") is not None:
        try:
            info_tag.setUserRating(int(info["userrating"]))
        except (ValueError, TypeError):
            pass
    if info.get("top250"):
        try:
            info_tag.setTop250(int(info["top250"]))
        except (ValueError, TypeError):
            pass
    if info.get("dbid"):
        try:
            info_tag.setDbId(int(info["dbid"]))
        except (ValueError, TypeError):
            pass
    
    # Rating with votes
    rating = info.get("rating")
    votes = info.get("votes", 0)
    if rating is not None:
        try:
            info_tag.setRating(float(rating), int(votes) if votes else 0, "default", True)
        except (ValueError, TypeError):
            pass
    
    # String fields
    if info.get("mpaa"):
        info_tag.setMpaa(str(info["mpaa"]))
    if info.get("tvshowtitle"):
        info_tag.setTvShowTitle(str(info["tvshowtitle"]))
    if info.get("imdbnumber"):
        info_tag.setIMDBNumber(str(info["imdbnumber"]))
    if info.get("trailer"):
        info_tag.setTrailer(str(info["trailer"]))
    if info.get("code"):
        info_tag.setProductionCode(str(info["code"]))
    if info.get("status") and str(info.get("mediatype") or "").lower() in ("tvshow", "season"):
        info_tag.setTvShowStatus(str(info["status"]))
    if info.get("path"):
        info_tag.setPath(str(info["path"]))
    if info.get("set"):
        info_tag.setSet(str(info["set"]))
    if info.get("setoverview"):
        info_tag.setSetOverview(str(info["setoverview"]))
    if info.get("album"):
        info_tag.setAlbum(str(info["album"]))
    
    # Date fields
    if info.get("premiered"):
        try:
            info_tag.setPremiered(str(info["premiered"]))
        except Exception:
            pass
    if info.get("aired"):
        try:
            info_tag.setFirstAired(str(info["aired"]))
        except Exception:
            pass
    if info.get("dateadded"):
        try:
            info_tag.setDateAdded(str(info["dateadded"]))
        except Exception:
            pass
    if info.get("lastplayed"):
        try:
            info_tag.setLastPlayed(str(info["lastplayed"]))
        except Exception:
            pass
    
    # List fields (need to be lists)
    if info.get("genre"):
        genres = info["genre"]
        if isinstance(genres, str):
            genres = [x.strip() for x in genres.split(",") if x.strip()]
        if isinstance(genres, (list, set)):
            info_tag.setGenres(list(genres))
    if info.get("country"):
        countries = info["country"]
        if isinstance(countries, str):
            countries = [x.strip() for x in countries.split(",") if x.strip()]
        if isinstance(countries, (list, set)):
            info_tag.setCountries(list(countries))
    if info.get("director"):
        directors = info["director"]
        if isinstance(directors, str):
            directors = [x.strip() for x in directors.split(",") if x.strip()]
        if isinstance(directors, (list, set)):
            info_tag.setDirectors(list(directors))
    if info.get("writer"):
        writers = info["writer"]
        if isinstance(writers, str):
            writers = [x.strip() for x in writers.split(",") if x.strip()]
        if isinstance(writers, (list, set)):
            info_tag.setWriters(list(writers))
    if info.get("studio"):
        studios = info["studio"]
        if isinstance(studios, str):
            studios = [s.strip() for s in studios.split(",") if s.strip()]
        if isinstance(studios, (list, set)):
            info_tag.setStudios(list(studios))
    if info.get("tag"):
        tags = info["tag"]
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",") if t.strip()]
        if isinstance(tags, (list, set)):
            info_tag.setTags(list(tags))
    if info.get("credits"):
        credits = info["credits"]
        if isinstance(credits, str):
            credits = [c.strip() for c in credits.split(",") if c.strip()]
        if isinstance(credits, (list, set)):
            info_tag.setWriters(list(credits))  # credits maps to writers
    if info.get("artist"):
        artists = info["artist"]
        if isinstance(artists, str):
            artists = [a.strip() for a in artists.split(",") if a.strip()]
        if isinstance(artists, (list, set)):
            info_tag.setArtists(list(artists))
    
    # Cast (needs xbmc.Actor objects)
    if cast:
        actors = normalize_cast_to_actors(cast)
        if actors:
            info_tag.setCast(actors)
    
    # Unique IDs
    if unique_ids and isinstance(unique_ids, dict):
        # Filter out None/empty values and ensure all values are strings
        clean_ids = {k: str(v) for k, v in unique_ids.items() if v}
        if clean_ids:
            info_tag.setUniqueIDs(clean_ids)
    
    # Handle named ratings (rating.tmdb, rating.imdb, rating.simkl, rating.tvdb, etc.)
    for key in info:
        if key.startswith("rating.") and isinstance(info[key], dict):
            rating_name = key.split(".")[1]  # e.g., "tmdb" from "rating.tmdb"
            try:
                rating_value = float(info[key].get("rating", 0.0))
                votes_value = int(info[key].get("votes", 0))
                info_tag.setRating(rating_value, votes_value, rating_name, False)
            except (ValueError, TypeError):
                pass


listitem_properties = [
    (("awards",), "Awards"),
    (("oscar_wins",), "Oscar_Wins"),
    (("oscar_nominations",), "Oscar_Nominations"),
    (("award_wins",), "Award_Wins"),
    (("award_nominations",), "Award_Nominations"),
    (("metacritic_rating",), "Metacritic_Rating"),
    (("rating.tmdb", "rating"), "TMDb_Rating"),
    (("rating.tmdb", "votes"), "TMDb_Votes"),
    (("rating.tvdb", "rating"), "Tvdb_Rating"),
    (("rating.tvdb", "votes"), "Tvdb_Votes"),
    (("rating.imdb", "rating"), "IMDb_Rating"),
    (("rating.imdb", "votes"), "IMDb_Votes"),
    (("rating.simkl", "rating"), "Simkl_Rating"),
    (("rating.simkl", "votes"), "Simkl_Votes"),
    (("rating.mal", "rating"), "MAL_Rating"),
    (("rating.mal", "votes"), "MAL_Votes"),
    (("rottentomatoes_rating",), "RottenTomatoes_Rating"),
    (("rottentomatoes_image",), "RottenTomatoes_Image"),
    (("rottentomatoes_reviewstotal",), "RottenTomatoes_ReviewsTotal"),
    (("rottentomatoes_reviewsfresh",), "RottenTomatoes_ReviewsFresh"),
    (("rottentomatoes_reviewsrotten",), "RottenTomatoes_ReviewsRotten"),
    (("rottentomatoes_consensus",), "RottenTomatoes_Consensus"),
    (("rottentomatoes_usermeter",), "RottenTomatoes_UserMeter"),
    (("rottentomatoes_userreviews",), "RottenTomatoes_UserReviews"),
]


class GlobalVariables:
    CONTENT_MENU = ""
    CONTENT_FILES = "files"
    CONTENT_MOVIE = "movies"
    CONTENT_SHOW = "tvshows"
    CONTENT_ANIME = "anime"
    CONTENT_SEASON = "seasons"
    CONTENT_EPISODE = "episodes"
    CONTENT_GENRES = "genres"
    CONTENT_YEARS = "years"
    CONTENT_ACTORS = "actors"
    MEDIA_MENU = ""
    MEDIA_FOLDER = "file"
    MEDIA_MOVIE = "movie"
    MEDIA_SHOW = "tvshow"
    MEDIA_SEASON = "season"
    MEDIA_EPISODE = "episode"

    SEMVER_REGEX = re.compile(r"^((?:\d+\.){2}\d+)")

    def __init__(self):
        self.IS_ADDON_FIRSTRUN = None
        self.ADDON = None
        self.ADDON_DATA_PATH = None
        self.ADDON_ID = None
        self.ADDON_NAME = None
        self.VERSION = None
        self.CLEAN_VERSION = None
        self.USER_AGENT = None
        self.DEFAULT_FANART = None
        self.DEFAULT_ICON = None
        self.DEFAULT_LOGO = None
        self.DEFAULT_POSTER = None
        self.NEXT_PAGE_ICON = None
        self.ADDON_USERDATA_PATH = None
        self.SETTINGS_CACHE = None
        self.RUNTIME_SETTINGS_CACHE = None
        self.LANGUAGE_CACHE = {}
        self.PLAYLIST = None
        self.HOME_WINDOW = None
        self.KODI_DATE_LONG_FORMAT = None
        self.KODI_DATE_SHORT_FORMAT = None
        self.KODI_TIME_FORMAT = None
        self.KODI_TIME_NO_SECONDS_FORMAT = None
        self.KODI_FULL_VERSION = None
        self.KODI_VERSION = None
        self.PLATFORM = self._get_system_platform()
        self.UTC_TIMEZONE = pytz.utc
        self.LOCAL_TIMEZONE = None
        self.URL = None
        self.PLUGIN_HANDLE = 0
        self.IS_SERVICE = True
        self.BASE_URL = None
        self.PATH = None
        self.PARAM_STRING = None
        self.REQUEST_PARAMS = None
        self.FROM_WIDGET = False
        self.PAGE = 1
        self.smart_scroll_index = None
        self.smart_scroll_trailing_extra = 0

    def __del__(self):
        self.deinit()

    def deinit(self):
        # Keep ADDON alive while prefetch threads (and their enrich workers) are still running.
        try:
            from resources.lib.modules.page_prefetch import prefetch_threads_active

            if not prefetch_threads_active():
                self.ADDON = None
        except Exception:
            self.ADDON = None
        self.PLAYLIST = None
        self.HOME_WINDOW = None

    def ensure_addon(self):
        """Re-bind xbmcaddon when a background thread outlives the plugin request."""
        addon = getattr(self, "ADDON", None)
        if addon is not None:
            return
        self.ADDON = xbmcaddon.Addon()
        if not getattr(self, "ADDON_ID", None):
            self.ADDON_ID = self.ADDON.getAddonInfo("id")
        if not getattr(self, "ADDON_NAME", None):
            self.ADDON_NAME = self.ADDON.getAddonInfo("name")
        if not getattr(self, "VERSION", None):
            self.VERSION = self.ADDON.getAddonInfo("version")
        if not getattr(self, "SETTINGS_CACHE", None):
            self._init_settings_cache()

    def init_globals(self, argv=None, addon_id=None):
        self.IS_ADDON_FIRSTRUN = self.IS_ADDON_FIRSTRUN is None
        self.ADDON = xbmcaddon.Addon()
        self.ADDON_ID = addon_id or self.ADDON.getAddonInfo("id")
        self.ADDON_NAME = self.ADDON.getAddonInfo("name")
        self.VERSION = self.ADDON.getAddonInfo("version")
        self.CLEAN_VERSION = self.SEMVER_REGEX.findall(self.VERSION)[0]
        self.USER_AGENT = f"{self.ADDON_NAME} - {self.CLEAN_VERSION}"
        self._init_kodi()
        self._init_settings_cache()
        self._init_local_timezone()
        self._init_paths()
        from resources.lib.modules.settings_hot_cache import warm_settings_dict

        warm_settings_dict()
        self.DEFAULT_FANART = self.ADDON.getAddonInfo("fanart")
        self.DEFAULT_ICON = self.ADDON.getAddonInfo("icon")
        self.DEFAULT_LOGO = f"{self.IMAGES_PATH}logo-prism-4.png"
        self.DEFAULT_POSTER = f"{self.IMAGES_PATH}poster-prism-4.png"
        self.NEXT_PAGE_ICON = f"{self.ICONS_PATH}next.png"
        self.init_request(argv)
        self._init_cache()
        # Warm session caches from the background service only — not every RunPlugin list open.
        if self.PLUGIN_HANDLE <= 0:
            try:
                from resources.lib.modules.prism_version import do_version_change

                do_version_change()
            except Exception:
                self.log_stacktrace()

    def _init_kodi(self):
        self.PLAYLIST = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)
        self.HOME_WINDOW = xbmcgui.Window(10000)
        self.KODI_DATE_LONG_FORMAT = xbmc.getRegion("datelong")
        self.KODI_DATE_SHORT_FORMAT = xbmc.getRegion("dateshort")
        self.KODI_TIME_FORMAT = xbmc.getRegion("time")
        self.KODI_TIME_NO_SECONDS_FORMAT = self.KODI_TIME_FORMAT.replace(":%S", "")
        self.KODI_FULL_VERSION = xbmc.getInfoLabel("System.BuildVersion")
        if version := re.findall(r'(?:(?:((?:\d+\.?){1,3}\S+))?\s+\(((?:\d+\.?){2,3})\))', self.KODI_FULL_VERSION):
            self.KODI_FULL_VERSION = version[0][1]
            if len(version[0][0]) > 1:
                pre_ver = version[0][0][:2]
                full_ver = version[0][1][:2]
                if pre_ver > full_ver:
                    self.KODI_VERSION = int(pre_ver[:2])
                else:
                    self.KODI_VERSION = int(full_ver[:2])
            else:
                self.KODI_VERSION = int(version[0][1][:2])
        else:
            self.KODI_FULL_VERSION = self.KODI_FULL_VERSION.split(' ')[0]
            self.KODI_VERSION = int(self.KODI_FULL_VERSION[:2])

    def _init_settings_cache(self):
        self.RUNTIME_SETTINGS_CACHE = RuntimeSettingsCache()
        self.SETTINGS_CACHE = PersistedSettingsCache()

    def _init_local_timezone(self):
        try:
            timezone_string = self.get_setting("general.localtimezone")
            if timezone_string:
                self.LOCAL_TIMEZONE = pytz.timezone(timezone_string)
        except pytz.UnknownTimeZoneError:
            self.log(f"Invalid local timezone '{timezone_string}' in settings.xml", "debug")
        except Exception as e:
            self.log(f"Error using local timezone '{timezone_string}' in settings.xml: {e}", "warning")
        finally:
            if not self.LOCAL_TIMEZONE or self.LOCAL_TIMEZONE == self.UTC_TIMEZONE:
                self.init_local_timezone()

    def init_local_timezone(self):
        """
        Attempts to detect the local timezone via a variety of approaches
        Initializes LOCAL_TIMEZONE to correct tzinfo value
        If this fails we should just use UTC as lack of any LOCAL_TIMEZONE will cause many failures
        :return: None
        """
        timezone_string = None
        try:
            cached = self.get_setting("general.localtimezone")
            if cached:
                try:
                    cached_tz = pytz.timezone(cached)
                    if cached_tz != self.UTC_TIMEZONE:
                        self.LOCAL_TIMEZONE = cached_tz
                        return
                except pytz.UnknownTimeZoneError:
                    self.log(f"Invalid cached local timezone '{cached}', re-detecting", "debug")

            response = self.json_rpc(
                "Settings.GetSettingValue",
                {"setting": "locale.timezone"},
                log_error=False,
            )
            timezone_string = response.get("value")
            if timezone_string:
                try:
                    self.LOCAL_TIMEZONE = pytz.timezone(timezone_string)
                except pytz.UnknownTimeZoneError:
                    self.log(
                        f"Kodi provided an invalid local timezone '{timezone_string}', trying a different approach",
                        "warning",
                    )
            # If Kodi detection failed, fall back on tzlocal
            try:
                if not self.LOCAL_TIMEZONE or self.LOCAL_TIMEZONE == self.UTC_TIMEZONE:
                    from resources.lib.third_party import tzlocal

                    self.LOCAL_TIMEZONE = tzlocal.get_localzone()
            except Exception as e:
                self.log(f"Error detecting local timezone with alternative approach: {e}", "warning")
            # If we still don't have a timezone, try manual setting
            try:
                if not self.LOCAL_TIMEZONE or self.LOCAL_TIMEZONE == self.UTC_TIMEZONE:
                    g.set_setting("general.manualtimezone", True)
                    timezone_string = self.get_setting("general.localtimezone")
                    if timezone_string:
                        self.LOCAL_TIMEZONE = pytz.timezone(timezone_string)
                else:
                    g.set_setting("general.manualtimezone", False)
            except pytz.UnknownTimeZoneError:
                self.log(f"Invalid local timezone '{timezone_string}' in settings.xml", "debug")
            except Exception as e:
                self.log(f"Error using local timezone '{timezone_string}' in settings.xml: {e}", "warning")
        finally:
            # If Kodi and tzocal detection fails and we don't have a valid manual setting, fallback to UTC
            if not self.LOCAL_TIMEZONE:
                self.LOCAL_TIMEZONE = self.UTC_TIMEZONE
            if self.LOCAL_TIMEZONE == self.UTC_TIMEZONE:
                self.log(
                    "Unable to detect local timezone, defaulting to UTC for displayed dates/times. "
                    "Note that this does not affect filtering or sorting, only display",
                    "debug",
                )
            self.set_setting("general.localtimezone", self.LOCAL_TIMEZONE.zone)

    @staticmethod
    def _get_system_platform():
        """
        get platform on which xbmc run
        """
        platform = "unknown"
        if xbmc.getCondVisibility("system.platform.android"):
            platform = "android"
        elif xbmc.getCondVisibility("system.platform.linux"):
            platform = "linux"
        elif xbmc.getCondVisibility("system.platform.xbox"):
            platform = "xbox"
        elif xbmc.getCondVisibility("system.platform.windows"):
            platform = "xbox" if "Users\\UserMgr" in os.environ.get("TMP") else "windows"
        elif xbmc.getCondVisibility("system.platform.osx"):
            platform = "osx"

        return platform

    def _init_cache(self):
        from resources.lib.database.cache import Cache

        self.CACHE = Cache()

    def init_request(self, argv):
        if argv is None:
            return

        self.URL = parse.urlparse(argv[0])
        try:
            self.PLUGIN_HANDLE = int(argv[1])
            self.IS_SERVICE = False
        except IndexError:
            self.PLUGIN_HANDLE = 0
            self.IS_SERVICE = True

        self.BASE_URL = f"{self.URL[0]}://{self.URL[1]}" if self.URL[1] != "" else ""
        self.PATH = parse.unquote(self.URL[2])
        try:
            self.PARAM_STRING = argv[2].lstrip('?/')
        except IndexError:
            self.PARAM_STRING = ""
        self.REQUEST_PARAMS = self.legacy_params_converter(dict(parse.parse_qsl(self.PARAM_STRING)))
        if "action_args" in self.REQUEST_PARAMS:
            self.REQUEST_PARAMS["action_args"] = tools.deconstruct_action_args(self.REQUEST_PARAMS["action_args"])
            if isinstance(self.REQUEST_PARAMS["action_args"], dict):
                self.REQUEST_PARAMS["action_args"] = self.legacy_action_args_converter(
                    self.REQUEST_PARAMS["action_args"]
                )
                from resources.lib.simkl.ids import normalize_action_args

                self.REQUEST_PARAMS["action_args"] = normalize_action_args(self.REQUEST_PARAMS["action_args"])
        self.FROM_WIDGET = not self.is_addon_visible() and self.PLUGIN_HANDLE > 0
        self.PAGE = int(g.REQUEST_PARAMS.get("page", 1))

    @staticmethod
    def legacy_action_args_converter(action_args):
        if "item_type" not in action_args:
            return action_args

        if "season" in action_args["item_type"]:
            from resources.lib.database.session import get_sync_database

            action_args.update(
                get_sync_database().get_season_action_args(action_args["simkl_id"], action_args["season"])
            )

        if "episode" in action_args["item_type"]:
            from resources.lib.database.session import get_sync_database

            action_args.update(
                get_sync_database().get_episode_action_args(
                    action_args["simkl_id"],
                    action_args["season"],
                    action_args["episode"],
                )
            )

        if "show" in action_args["item_type"]:
            action_args["item_type"] = "shows"

        action_args["mediatype"] = action_args.pop("item_type")
        return action_args

    @staticmethod
    def legacy_params_converter(params):
        if "actionArgs" in params:
            params["action_args"] = params.pop("actionArgs")
        if "action" in params:
            if params["action"] == "moviesTrending":
                params["action"] = "genericEndpoint"
                params["endpoint"] = "trending"
                params["mediatype"] = "movies"
            if params["action"] == "moviesPopular":
                params["action"] = "genericEndpoint"
                params["endpoint"] = "popular"
                params["mediatype"] = "movies"
            if params["action"] == "moviesWatched":
                params["action"] = "genericEndpoint"
                params["endpoint"] = "watched"
                params["mediatype"] = "movies"
            if params["action"] == "moviesAnticipated":
                params["action"] = "genericEndpoint"
                params["endpoint"] = "anticipated"
                params["mediatype"] = "movies"
            if params["action"] == "moviesBoxOffice":
                params["action"] = "genericEndpoint"
                params["endpoint"] = "boxoffice"
                params["mediatype"] = "movies"
            if params["action"] == "showsTrending":
                params["action"] = "genericEndpoint"
                params["endpoint"] = "trending"
                params["mediatype"] = "shows"
            if params["action"] == "showsPopular":
                params["action"] = "genericEndpoint"
                params["endpoint"] = "popular"
                params["mediatype"] = "shows"
            if params["action"] == "showsWatched":
                params["action"] = "genericEndpoint"
                params["endpoint"] = "watched"
                params["mediatype"] = "shows"
            if params["action"] == "showsAnticipated":
                params["action"] = "genericEndpoint"
                params["endpoint"] = "anticipated"
                params["mediatype"] = "shows"
            if params["action"] == "showsBoxOffice":
                params["action"] = "genericEndpoint"
                params["endpoint"] = "boxoffice"
                params["mediatype"] = "shows"
        return params
        
    def get_easynews_credentials(self):
        """Get Easynews username and password from settings."""
        username = self.get_setting("easynews.username") or ""
        password = self.get_setting("easynews.password") or ""
        return (username.strip(), password.strip()) if username and password else (None, None)
        
    def _init_paths(self):
        self.ADDONS_PATH = tools.translate_path(os.path.join("special://home/", "addons/"))
        self.ADDON_PATH = tools.translate_path(os.path.join("special://home/", f"addons/{self.ADDON_ID.lower()}"))
        self.ADDON_DATA_PATH = tools.translate_path(self.ADDON.getAddonInfo("path"))  # Addon folder
        self.ADDON_USERDATA_PATH = tools.translate_path(
            f"special://profile/addon_data/{self.ADDON_ID}/"
        )  # Addon user data folder
        self.SETTINGS_PATH = tools.translate_path(os.path.join(self.ADDON_USERDATA_PATH, "settings.xml"))
        self.ADVANCED_SETTINGS_PATH = tools.translate_path("special://profile/advancedsettings.xml")
        self.KODI_DATABASE_PATH = tools.translate_path("special://database/")
        self.GUI_PATH = tools.translate_path(os.path.join(self.ADDON_DATA_PATH, "resources", "lib", "gui"))
        self.IMAGES_PATH = f"{self.ADDON.getAddonInfo('path')}/resources/images/"
        # Icon pack: 0 = colored (default), 1 = white. Menus/genres share the same filenames.
        self.ICON_PACK = "white" if self.get_int_setting("general.iconpack", 0) == 1 else "colored"
        self.ICONS_PATH = f"{self.IMAGES_PATH}{self.ICON_PACK}/icons/"
        self.GENRES_PATH = f"{self.IMAGES_PATH}{self.ICON_PACK}/genres/"
        self.SHARED_GENRES_PATH = f"{self.IMAGES_PATH}shared/genres/"
        self.SKINS_PATH = tools.translate_path(os.path.join(self.ADDON_USERDATA_PATH, "skins"))
        self.CACHE_DB_PATH = tools.translate_path(os.path.join(self.ADDON_USERDATA_PATH, "cache.db"))
        self.TORRENT_CACHE = tools.translate_path(os.path.join(self.ADDON_USERDATA_PATH, "torrentCache.db"))
        self.DEBRID_CACHE_DB_PATH = tools.translate_path(os.path.join(self.ADDON_USERDATA_PATH, "debridCache.db"))
        self.TORRENT_ASSIST = tools.translate_path(os.path.join(self.ADDON_USERDATA_PATH, "torentAssist.db"))
        self.PROVIDER_CACHE_DB_PATH = tools.translate_path(os.path.join(self.ADDON_USERDATA_PATH, "providers.db"))
        self.PREMIUMIZE_DB_PATH = tools.translate_path(os.path.join(self.ADDON_USERDATA_PATH, "premiumize.db"))
        self.SIMKL_SYNC_DB_PATH = tools.translate_path(os.path.join(self.ADDON_USERDATA_PATH, "simklSync.db"))
        self.PRISM_META_DB_PATH = tools.translate_path(os.path.join(self.ADDON_USERDATA_PATH, "prism_meta.db"))
        self.CONTEXT_ADDON_ID = "context.prism"
        self.CONTEXT_ADDON_PATH = tools.translate_path(
            os.path.join("special://home/addons/", self.CONTEXT_ADDON_ID)
        )
        self.INFO_DB_PATH = os.path.join(self.CONTEXT_ADDON_PATH, "info.db")
        self.SEARCH_HISTORY_DB_PATH = tools.translate_path(os.path.join(self.ADDON_USERDATA_PATH, "search.db"))
        self.SKINS_DB_PATH = tools.translate_path(os.path.join(self.ADDON_USERDATA_PATH, "skins.db"))

    def get_kodi_video_db_connection(self, max_lock_retries=50, read_only=False):
        config = self.get_kodi_video_db_config()
        if config["type"] == "sqlite3":
            from resources.lib.database import KodiMyVideosReadConnection, SQLiteConnection

            path = os.path.join(self.KODI_DATABASE_PATH, f"{config['database']}.db")
            if read_only:
                return KodiMyVideosReadConnection(path, max_lock_retries=max_lock_retries)
            return SQLiteConnection(path, max_lock_retries=max_lock_retries)
        elif config["type"] == "mysql":
            from resources.lib.database import MySqlConnection

            return MySqlConnection(config)

    def get_kodi_database_version(self):
        kodi_myvideos_version_map = {
            17: 107,
            18: 116,
            19: 119,
            20: 121,
            21: 131,
            22: 146,
        }

        if (db_version := kodi_myvideos_version_map.get(self.KODI_VERSION)) is not None:
            return db_version

        detected = self._detect_myvideos_db_version()
        if detected is not None:
            return detected

        raise KeyError(f"Unsupported kodi version {self.KODI_VERSION}")

    def _detect_myvideos_db_version(self) -> int | None:
        """Pick the highest MyVideos schema present (covers Kodi alphas with bumped DB versions)."""
        import re

        highest = 0
        pattern = re.compile(r"^MyVideos(\d+)\.db$", re.IGNORECASE)
        try:
            if not xbmcvfs.exists(self.KODI_DATABASE_PATH):
                return None
            for name in xbmcvfs.listdir(self.KODI_DATABASE_PATH):
                match = pattern.match(name)
                if match:
                    highest = max(highest, int(match.group(1)))
        except Exception:
            self.log_stacktrace()
            return None
        if highest > 0:
            self.log(
                f"Resolved MyVideos{highest} from database folder for Kodi {self.KODI_VERSION}",
                "debug",
            )
            return highest
        return None

    def get_kodi_video_db_config(self):
        result = {"type": "sqlite3", "database": f"MyVideos{self.get_kodi_database_version()}"}

        if xbmcvfs.exists(self.ADVANCED_SETTINGS_PATH):
            if advanced_settings_text := g.read_all_text(self.ADVANCED_SETTINGS_PATH):
                try:
                    advanced_settings = ElementTree.fromstring(advanced_settings_text)
                    if settings := advanced_settings.find("videodatabase"):
                        for setting in settings:
                            if setting.tag == 'type':
                                result["type"] = setting.text
                            elif setting.tag == 'host':
                                result["host"] = setting.text
                            elif setting.tag == 'port':
                                result["port"] = setting.text
                            elif setting.tag == 'name':
                                result["database"] = setting.text
                            elif setting.tag == 'user':
                                result["user"] = setting.text
                            elif setting.tag == 'pass':
                                result["password"] = setting.text
                except ElementTree.ParseError as pe:
                    g.log(f"Failed to parse advanced settings.xml: {pe}", "warning")
        return result

    def clear_kodi_bookmarks(self, max_lock_retries=5):
        """Remove stale Kodi-native resume bookmarks for Prism plugin URLs (not watched-only rows)."""
        import sqlite3

        try:
            with self.get_kodi_video_db_connection(max_lock_retries=max_lock_retries) as video_database:
                config = self.get_kodi_video_db_config()
                if config.get("type") == "mysql":
                    rows = video_database.fetchall(
                        """
                        SELECT DISTINCT f.idFile
                        FROM files f
                        INNER JOIN bookmark b ON b.idFile = f.idFile
                        WHERE f.strFilename LIKE %s
                        """,
                        ("%plugin.video.prism%",),
                    )
                else:
                    rows = video_database.fetchall(
                        """
                        SELECT DISTINCT f.idFile
                        FROM files f
                        INNER JOIN bookmark b ON b.idFile = f.idFile
                        WHERE f.strFilename LIKE '%plugin.video.prism%'
                        """
                    )
                if file_ids := [str(i["idFile"]) for i in rows]:
                    video_database.execute_sql(
                        [
                            f"DELETE FROM {table} WHERE idFile IN ({','.join(file_ids)})"
                            for table in ["bookmark", "streamdetails", "files"]
                        ]
                    )
        except sqlite3.OperationalError:
            self.log("Skipping Kodi bookmark cleanup; video database is locked", "debug")

    # region runtime settings
    def set_runtime_setting(self, setting_id, value):
        """
        Set a runtime setting value

        Lists and Dict may only contain simple types

        :param setting_id: The name of the setting
        :type setting_id: str
        :param value: The value to store in settings
        :type value: str|float|int|bool|list|dict
        """
        self.RUNTIME_SETTINGS_CACHE.set_setting(setting_id, value)

    def clear_runtime_setting(self, setting_id):
        """
        Clear a runtime setting from the cache.

        :param setting_id: The name of the setting
        :type setting_id: str
        """
        self.RUNTIME_SETTINGS_CACHE.clear_setting(setting_id)

    def get_runtime_setting(self, setting_id, default_value=None):
        """
        Get a runtime setting value

        :param setting_id: The name of the setting
        :type setting_id: str
        :param default_value: An optional default value to provide if the setting is not stored
        :type default_value: str|float|int|bool
        :return: The value of the setting.
                 If the setting is not stored, the optional default_value if provided or None
        :rtype: str|float|int|bool|list|dict
        """
        return self.RUNTIME_SETTINGS_CACHE.get_setting(setting_id, default_value)

    def get_float_runtime_setting(self, setting_id, default_value=None):
        """
        Get a runtime setting as a float value

Due to message length limits, continuing the file in the next call.