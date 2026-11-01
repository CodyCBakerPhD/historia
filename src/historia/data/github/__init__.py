"""
Fetch a user's GitHub activity and save it to disk, one JSON file per day and info type.

- ``update`` refreshes the most recent days, and is what ``historia update github`` runs.
- ``dump_info_for_date`` saves every info type for one day, and ``dump_specific_info`` saves one of them.
- ``fetch_info_for_date`` returns the URLs for one info type on one day without saving them.
- ``CACHE_LAYOUT_VERSION`` numbers the on-disk layout, which files are saved under as ``version-<N>``.
"""

from ._fetch_info import fetch_info_for_date
from ._dump import CACHE_LAYOUT_VERSION, dump_info_for_date, dump_specific_info
from ._update import update

__all__ = ["CACHE_LAYOUT_VERSION", "dump_info_for_date", "dump_specific_info", "fetch_info_for_date", "update"]
