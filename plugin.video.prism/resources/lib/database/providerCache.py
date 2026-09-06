"""
Simple on-disk provider cache used to store provider-specific cloud/debrid results
with pre-computed folder and episode token fields to speed up three-pass matching.

This is intentionally lightweight and JSON backed for portability.
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional, Tuple

from resources.lib.common import source_utils
from resources.lib.common import tools
from resources.lib.modules.globals import g

_CACHE_FILENAME = "provider_cache.json"


def _cache_path() -> str:
    """Filesystem path for provider cache in userdata."""
    userdata = (g.ADDON_USERDATA_PATH or "").rstrip("/\\")
    return tools.validate_path(os.path.join(userdata, _CACHE_FILENAME))


def _immediate_parent_folder(path: str) -> Optional[str]:
    if not path:
        return None
    parts = [p for p in str(path).replace("\\", "/").split("/") if p]
    if len(parts) >= 2:
        return parts[-2]
    return None


class ProviderCache:
    """
    Minimal provider cache.

    Storage layout (JSON):
    {
        "<provider_key>": [
            {
                "id": "<optional id>",
                "path": "...",
                "release_title": "...",
                "url": "...",
                "folder_name": "...",
                "se_tokens": [[1,2], [1,3]],
                "bare_episodes": [15,48],
                "episode_title_tokens": ["river","dale"],
                ... original provider fields preserved ...
            },
            ...
        ],
        ...
    }
    """

    def __init__(self):
        self._path = _cache_path()
        self._cache: Dict[str, List[Dict[str, Any]]] = {}
        self._load()

    # -------------------
    # Persistence
    # -------------------
    def _load(self) -> None:
        try:
            if not os.path.exists(self._path):
                self._cache = {}
                return
            with open(self._path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
                # Ensure dict structure
                if isinstance(data, dict):
                    self._cache = data
                else:
                    self._cache = {}
        except Exception as exc:  # pragma: no cover - defensive
            g.log(f"ProviderCache: load failed: {exc}", "warning")
            self._cache = {}

    def _save(self) -> None:
        try:
            userdata_dir = os.path.dirname(self._path)
            if userdata_dir and not os.path.exists(userdata_dir):
                os.makedirs(userdata_dir, exist_ok=True)
            with open(self._path, "w", encoding="utf-8") as fh:
                json.dump(self._cache, fh, indent=2, ensure_ascii=False)
        except Exception as exc:  # pragma: no cover - defensive
            g.log(f"ProviderCache: save failed: {exc}", "error")

    # -------------------
    # Normalization helpers
    # -------------------
    @staticmethod
    def _compute_se_tokens(text: str) -> List[Tuple[int, int]]:
        out: List[Tuple[int, int]] = []
        for s, e in source_utils.iter_season_episode_tokens(text or ""):
            try:
                out.append((int(s), int(e)))
            except Exception:
                continue
        return out

    @staticmethod
    def _compute_bare_episodes(text: str) -> List[int]:
        out: List[int] = []
        for n in source_utils.iter_bare_episode_numbers(text or ""):
            try:
                out.append(int(n))
            except Exception:
                continue
        return out

    @staticmethod
    def _compute_episode_title_tokens(ep_title: Optional[str]) -> List[str]:
        return sorted(list(source_utils.episode_title_keep_tokens(ep_title or "")))

    def _normalize_entry(self, entry: Dict[str, Any]) -> Dict[str, Any]:
        """
        Ensure the entry has the computed token fields. Does not remove other provider fields.
        """
        e = dict(entry)  # shallow copy
        # candidate text to scan: prefer explicit fields; fallback to full path/name
        candidate = ""
        for k in ("path", "release_title", "name", "short_name", "url"):
            v = e.get(k)
            if isinstance(v, str) and v.strip():
                candidate = f"{candidate} {v}".strip()
        # folder name extraction
        if not e.get("folder_name"):
            folder = _immediate_parent_folder(e.get("path") or e.get("url") or "")
            e["folder_name"] = folder or e.get("folder_name") or ""
        # tokens
        e["se_tokens"] = self._compute_se_tokens(candidate)
        e["bare_episodes"] = self._compute_bare_episodes(candidate)
        # If provider supplied an episode_title context, compute tokens from it
        supplied_ep_title = e.get("episode_title") or e.get("ep_title") or ""
        e["episode_title_tokens"] = self._compute_episode_title_tokens(supplied_ep_title)
        return e

    # -------------------
    # Public API
    # -------------------
    def get_provider_packages(self) -> List[str]:
        """Return list of provider keys currently in cache (keeps compatibility)."""
        return list(self._cache.keys())

    def get_cached_items(self, provider_key: str) -> List[Dict[str, Any]]:
        """
        Return cached items for provider_key. Normalizes token fields on read.
        """
        items = self._cache.get(provider_key) or []
        normalized = []
        for i in items:
            try:
                normalized.append(self._normalize_entry(i))
            except Exception:
                normalized.append(i)
        # keep normalized state in memory for future reads
        self._cache[provider_key] = normalized
        return normalized

    def set_cached_items(self, provider_key: str, items: List[Dict[str, Any]]) -> None:
        """Overwrite cached items for provider_key and persist to disk."""
        normalized = [self._normalize_entry(i) for i in items]
        self._cache[provider_key] = normalized
        self._save()

    def add_or_update_item(self, provider_key: str, item: Dict[str, Any], id_field: str = "id") -> None:
        """
        Add or update a single item. Uses id_field to detect existing entry.
        If id not present or no match found, appends.
        """
        lst = self._cache.get(provider_key, []) or []
        new_e = self._normalize_entry(item)
        ident = new_e.get(id_field)
        if ident:
            for idx, existing in enumerate(lst):
                if existing.get(id_field) and str(existing.get(id_field)) == str(ident):
                    lst[idx] = new_e
                    self._cache[provider_key] = lst
                    self._save()
                    return
        lst.append(new_e)
        self._cache[provider_key] = lst
        self._save()

    def clear_provider(self, provider_key: str) -> None:
        """Remove cached entries for a provider."""
        if provider_key in self._cache:
            del self._cache[provider_key]
            self._save()

    def validate_entry_against_request(self, entry: Dict[str, Any], simple_info: Dict[str, Any]) -> bool:
        """
        Re-validate a cached entry against a requested simple_info according to the
        three-pass matching rules:
          1. Folder gate first -> if folder present and doesn't match -> reject
          2. Episode-title tokens override -> accept if present in filename
          3. Malformed EP declarations reject unless episode-title override
          4. S#E# token matching (exact) with protected_placement_guard
          5. Bare episode fallback with protected_placement_guard
          6. Absolute number fallback (padded variants) with protected_placement_guard
        """
        if not isinstance(entry, dict) or not isinstance(simple_info, dict):
            return False

        # Prepare normalized candidate string
        candidate = ""
        for k in ("path", "release_title", "name", "short_name", "url"):
            v = entry.get(k)
            if isinstance(v, str) and v.strip():
                candidate = f"{candidate} {v}".strip()
        cleaned_candidate = source_utils.clean_title(candidate)

        # Folder gate
        folder = entry.get("folder_name") or _immediate_parent_folder(entry.get("path") or entry.get("url") or "")
        if folder:
            try:
                if not source_utils.folder_name_matches(folder, simple_info):
                    # folder exists but does not match show title/aliases -> reject
                    # however allow override via episode-title tokens (checked next)
                    ep_title = simple_info.get("episode_title")
                    if not (ep_title and source_utils.episode_title_in_release(ep_title, cleaned_candidate)):
                        return False
            except Exception:
                # If folder matching raises, be conservative and reject
                return False

        # Malformed declaration rejection (EP15p)
        if source_utils._malformed_ep_decl_re.search(cleaned_candidate):
            ep_title = simple_info.get("episode_title")
            if not (ep_title and source_utils.episode_title_in_release(ep_title, cleaned_candidate)):
                return False

        # Episode-title token override (highest priority)
        ep_title = simple_info.get("episode_title")
        if ep_title and source_utils.episode_title_in_release(ep_title, cleaned_candidate):
            return True

        # Requested coords
        req_s = simple_info.get("season_number") or simple_info.get("season") or ""
        req_e = simple_info.get("episode_number") or simple_info.get("episode") or ""
        try:
            req_s_i = int(str(req_s)) if req_s not in (None, "") else None
        except Exception:
            req_s_i = None
        try:
            req_e_i = int(str(req_e)) if req_e not in (None, "") else None
        except Exception:
            req_e_i = None

        # 1) Explicit se_tokens
        for s, e in entry.get("se_tokens", []) if isinstance(entry.get("se_tokens"), list) else []:
            try:
                if req_s_i is not None and req_e_i is not None:
                    if int(s) == int(req_s_i) and int(e) == int(req_e_i):
                        if source_utils.protected_placement_guard(cleaned_candidate, simple_info):
                            return True
                else:
                    # No requested season/episode; accept if placement guard passes and show title prefix found
                    if source_utils.protected_placement_guard(cleaned_candidate, simple_info):
                        return True
            except Exception:
                continue

        # 2) Bare episodes
        for n in entry.get("bare_episodes", []) if isinstance(entry.get("bare_episodes"), list) else []:
            try:
                if req_e_i is not None and int(n) == req_e_i:
                    if source_utils.protected_placement_guard(cleaned_candidate, simple_info):
                        return True
            except Exception:
                continue

        # 3) Absolute number fallback
        abs_num = simple_info.get("absolute_number")
        if abs_num not in (None, ""):
            try:
                abs_req = int(str(abs_num))
                padded = str(abs_req).zfill(3)
                haystack = f" {cleaned_candidate} "
                for needle in (
                    f" {padded} ",
                    f" {abs_req} ",
                    f"-{padded}-",
                    f"-{abs_req}-",
                    f" e{abs_req} ",
                    f" ep{abs_req} ",
                    f" episode {abs_req} ",
                ):
                    if needle in haystack and source_utils.protected_placement_guard(cleaned_candidate, simple_info):
                        return True
            except Exception:
                pass

        # Not matched
        return False
