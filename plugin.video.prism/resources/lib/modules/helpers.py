import xbmcgui

from resources.lib.common import tools
from resources.lib.database.cache import use_cache
from resources.lib.database.providerCache import ProviderCache
from resources.lib.database.skinManager import SkinManager
from resources.lib.gui.windows.resolver_window import ResolverWindow
from resources.lib.modules.getSources import Sources
from resources.lib.modules.globals import g
from resources.lib.modules.resolver import Resolver
from resources.lib.modules.source_sorter import SourceSorter
from resources.lib.common import source_utils

def _valid_stream_link(stream_link) -> bool:
    return bool(stream_link) and stream_link != "none"


def _resolved_source_from_list(sources, release_title):
    if not release_title or not sources:
        return None
    for source in sources:
        if isinstance(source, dict) and source.get("release_title") == release_title:
            return source
    return None


class Resolverhelper:
    """
    Helper object to stream line resolving items
    """

    window = None

    @use_cache(1)
    def resolve_silent_or_visible(
        self,
        sources,
        item_information,
        pack_select=False,
        overwrite_cache=False,
        smart_play_context=False,
    ):
        """
        Method to handle automatic background or foreground resolving
        :param sources: list of sources to handle
        :param item_information: information on item to play
        :param pack_select: True if you want to perform a manual file selection
        :param overwrite_cache: Set to true if you wish to overwrite the current cached return value
        :param smart_play_context: True when Smart Play digit reorder was active for this resolve
        :return: None if unsuccessful otherwise a playable object
        """
        stream_link = None
        release_title = None
        resolved_source = None

        if g.get_bool_runtime_setting('tempSilent') or g.get_bool_setting("general.resolverHide", False):
            stream_link, release_title, resolved_source = Resolver().resolve_multiple_until_valid_link(
                sources, item_information, pack_select, True
            )
        else:
            self.window = ResolverWindow(
                *SkinManager().confirm_skin_path('resolver.xml'),
                item_information=item_information,
                close_callback=self.close_window,
            )
            tools.run_threaded(self.window.doModal, sources, pack_select)
            while not g.wait_for_abort(0.30):
                stream_link, release_title = self.window.get_return_data()
                if _valid_stream_link(stream_link):
                    resolved_source = _resolved_source_from_list(sources, release_title)
                    break

        if not _valid_stream_link(stream_link):
            stream_link = None

        if item_information['info']['mediatype'] == g.MEDIA_EPISODE and release_title:
            from resources.lib.simkl.ids import release_title_cache_key

            cache_key = release_title_cache_key(item_information["info"])
            if cache_key:
                g.set_runtime_setting(cache_key, release_title)

        if smart_play_context and resolved_source:
            from resources.lib.modules.last_played_source import save_last_played_source

            save_last_played_source(resolved_source)
        return stream_link

    def close_window(self):
        if self.window:
            self.window.close()
            del self.window
            self.window = None


class SourcesHelper:
    """
    Helper object to stream line scraping of items
    """

    @use_cache(1)
    def get_sources(self, action_args, overwrite_cache=False):
        """
        Method to handle automatic background or foreground scraping
        :param action_args: action arguments from request uri
        :param overwrite_cache: Set to true if you wish to overwrite the current cached return value
        :return: (uncached, sources_list, item_information) or None when the user cancels
        """
        item_information = tools.get_item_information(action_args)
        if not ProviderCache().get_provider_packages():
            has_local_directory = g.configured_directory_path('local.location') or g.configured_directory_path(
                'download.location'
            )
            if not has_local_directory:
                yesno = xbmcgui.Dialog().yesno(g.ADDON_NAME, g.get_language_string(30443))
                if not yesno:
                    g.cancel_playback()
                    return None

        # Run the normal scraping flow
        uncached, sources_list, item_information = Sources(item_information).get_sources(overwrite_torrent_cache=overwrite_cache)

        # If this is an episode, apply early folder gate and compute match scores for ranking
        try:
            if item_information and item_information.get("info", {}).get("mediatype") == g.MEDIA_EPISODE:
                simple_info = self._build_simple_show_info(item_information)

                filtered_sources = []
                for src in sources_list:
                    # Safety: accept non-dict items
                    if not isinstance(src, dict):
                        filtered_sources.append(src)
                        continue

                    # Build candidate string for matching
                    candidate = ' '.join(str(src.get(k) or '') for k in ('path', 'release_title', 'name', 'short_name') if src.get(k))
                    candidate_clean = source_utils.clean_title(candidate)

                    # Folder gate: if folder exists and does not match, reject unless episode-title override
                    folder = None
                    try:
                        path = src.get('path') or src.get('url') or src.get('name') or ''
                        if path:
                            parts = [p for p in str(path).replace('\\', '/').split('/') if p]
                            if len(parts) >= 2:
                                folder = parts[-2]
                    except Exception:
                        folder = None

                    folder_ok = True
                    if folder:
                        folder_ok = source_utils.folder_name_matches(folder, simple_info)
                        # If folder doesn't match but episode-title tokens present in file, allow (override)
                        if not folder_ok:
                            ep_title = simple_info.get('episode_title')
                            if ep_title and source_utils.episode_title_in_release(ep_title, candidate_clean):
                                folder_ok = True

                    if not folder_ok:
                        # reject item
                        continue

                    # Malformed EP declarations: reject unless episode-title override
                    if source_utils._malformed_ep_decl_re.search(candidate_clean):
                        ep_title = simple_info.get('episode_title')
                        if not (ep_title and source_utils.episode_title_in_release(ep_title, candidate_clean)):
                            continue

                    # Attach a match_score for later ranking
                    try:
                        score = self._score_episode_match(candidate, simple_info)
                    except Exception:
                        score = 0
                    src['match_score'] = score

                    filtered_sources.append(src)

                sources_list = filtered_sources
        except Exception:
            # Be permissive on unexpected shapes
            pass

        return uncached, sources_list, item_information

    def sort_sources(
        self,
        item_information,
        sources_list,
        *,
        smart_play_context=False,
        source_select=False,
    ):
        """
        Method to handle source filtering, sorting and notifications
        :param item_information: The item information
        :type item_information: dict
        :param sources_list: the list of sources to be sorted
        :type sources_list list
        :param smart_play_context: Smart Play binge / pre-scrape context
        :param source_select: True when user picks from Source Select window
        :return: Filtered and Sorted sources
        :rtype: list
        """
        skip_last_release = bool(smart_play_context and not source_select)
        sorter = SourceSorter(item_information, skip_last_release_priority=skip_last_release)
        sources = sorter.sort_sources(sources_list)
        if sources is None or len(sources) < 1:
            g.cancel_playback()
            g.notification(g.ADDON_NAME, g.get_language_string(30032), time=5000)
            return

        # Apply match_score-based stable ordering on top of the sorter results (episode-specific)
        try:
            if item_information and item_information.get("info", {}).get("mediatype") == g.MEDIA_EPISODE:
                # Ensure every source has match_score (default 0)
                for s in sources:
                    if isinstance(s, dict):
                        s.setdefault('match_score', 0)
                # Stable sort: higher match_score first, keep previous order for ties
                sources = sorted(sources, key=lambda x: x.get('match_score', 0), reverse=True)
        except Exception:
            pass

        if (
            smart_play_context
            and not source_select
            and item_information.get("info", {}).get("mediatype") == g.MEDIA_EPISODE
        ):
            from resources.lib.simkl.ids import episode_num_from_info
            from resources.lib.modules.last_played_source import reorder_sources

            episode = episode_num_from_info(item_information["info"])
            if episode is not None:
                sources, matched = reorder_sources(sources, episode, source_select=source_select)
                if matched:
                    return sources
            if skip_last_release:
                sources = sorter.apply_last_release_name_fallback(sources)

        return sources

    # -------------------------
    # Helpers for scoring and simple_info
    # -------------------------
    @staticmethod
    def _build_simple_show_info(item_information):
        """Construct a simplified simple_info dict used by source_utils helpers."""
        info = (item_information or {}).get("info") or {}
        show_title = info.get('tvshowtitle') or info.get('title') or ''
        ep_title = info.get('originaltitle') or info.get('title') or ''
        season = info.get('season') or info.get('season_number') or ''
        episode = info.get('episode') or info.get('episode_number') or ''
        simple_info = {
            'show_title': show_title,
            'episode_title': ep_title,
            'year': str(info.get('tvshow.year', info.get('year', ''))),
            'season_number': str(season if season is not None else ''),
            'episode_number': str(episode if episode is not None else ''),
            'show_aliases': list(info.get('aliases', [])),
            'country': info.get('country_origin', '') or info.get('country'),
            'no_seasons': str(item_information.get('season_count', '')),
            'absolute_number': str(item_information.get('absoluteNumber') or item_information.get('absolute_number') or ''),
            'is_airing': item_information.get('is_airing', False),
            'no_episodes': str(item_information.get('episode_count', '')),
            'isanime': False,
        }
        return simple_info

    @staticmethod
    def _score_episode_match(candidate: str, simple_info: dict) -> int:
        """
        Rate files by:
          - Episode-title token match (highest, overrides S#E#): 100
          - Exact S#E# token match + protected placement: 90
          - Protected placement guard pass (medium): 60
          - Bare episode match + protected placement: 50
          - Malformed declaration penalty: -50
          - Default: 0
        """
        if not candidate:
            return 0
        r = source_utils.clean_title(candidate)

        # Episode-title tokens override highest
        ep_title = simple_info.get('episode_title')
        if ep_title and source_utils.episode_title_in_release(ep_title, r):
            return 100

        # Malformed declaration => heavy penalty unless episode-title override (already handled)
        if source_utils._malformed_ep_decl_re.search(r):
            return -50

        # Explicit S#E# tokens
        for s, e in source_utils.iter_season_episode_tokens(r):
            try:
                s_i, e_i = int(s), int(e)
            except Exception:
                continue
            req_s = simple_info.get('season_number') or simple_info.get('season')
            req_e = simple_info.get('episode_number') or simple_info.get('episode')
            try:
                req_s_i = int(str(req_s)) if req_s not in (None, '') else None
                req_e_i = int(str(req_e)) if req_e not in (None, '') else None
            except Exception:
                req_s_i = req_e_i = None

            if req_s_i is not None and req_e_i is not None:
                if s_i == req_s_i and e_i == req_e_i and source_utils.protected_placement_guard(r, simple_info):
                    return 90
            else:
                # No requested season/episode available; presence of SE token with title prefix is decent
                if source_utils.protected_placement_guard(r, simple_info):
                    return 60

        # Bare episode fallback
        for n in source_utils.iter_bare_episode_numbers(r):
            try:
                n_i = int(n)
            except Exception:
                continue
            req_e = simple_info.get('episode_number') or simple_info.get('episode')
            try:
                req_e_i = int(str(req_e)) if req_e not in (None, '') else None
            except Exception:
                req_e_i = None
            if req_e_i is not None and n_i == req_e_i and source_utils.protected_placement_guard(r, simple_info):
                return 50

        # Protected placement guard (title before token) gives modest score
        if source_utils.protected_placement_guard(r, simple_info):
            return 40

        return 0


def show_persistent_window_if_required(item_information):
    """
    Displays a constant window in the background, used to fill in gaps between windows dropping and opening
    :param item_information:
    :return: WindowDialog
    """
    if g.get_int_setting('general.scrapedisplay') != 0 or g.get_runtime_setting('tempSilent'):
        return None
    from resources.lib.database.skinManager import SkinManager
    from resources.lib.gui.windows.persistent_background import PersistentBackground

    background = PersistentBackground(
        *SkinManager().confirm_skin_path('persistent_background.xml'), item_information=item_information
    )
    background.set_text(g.get_language_string(30030))
    background.show()
    return background
