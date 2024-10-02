# This file is part of ranger, the console file manager.
# License: GNU GPL version 3, see the file "AUTHORS" for details.
"""Shared objects contain singletons for shared use."""
import typing
if typing.TYPE_CHECKING:
    import ranger.core.fm
    import ranger.container.settings


class FileManagerAware:  # pylint: disable=too-few-public-methods
    """Subclass this to gain access to the global "FM" object."""
    fm: typing.ClassVar[ 'ranger.core.fm.FM' ]

    @staticmethod
    def fm_set( fm: 'ranger.core.fm.FM' ) -> None:
        FileManagerAware.fm = fm


class SettingsAware:
    """Subclass this to gain access to the global "SettingObject" object."""
    settings: typing.ClassVar[ 'ranger.container.settings.Settings' ]

    @staticmethod
    def settings_set( settings: 'ranger.container.settings.Settings' ) -> None:
        SettingsAware.settings = settings
