"""
API-compatible stand-in of the mod dependency installer.

Upstream this is ``alasio/deploy/simple_pip/install_base.py`` (318 lines,
``InstallBase``), which alone drags in the whole deploy stack: ``simple_pip``
(3023 lines), ``deploy/pack`` (5910 lines) and ``deploy/httpclient`` (2683
lines). None of that is ported yet, while
``oas/backend/app/restart/restart_step.py`` -- kept verbatim from upstream --
imports ``InstallBase`` and calls exactly three things on it:

    install = InstallBase(mod, local_site_packages(), client=self.update_check.client())
    result = await install.install_pack()      # dict[str, bool], one entry per dependency
    await install.cleanup_dist_info()          # after the whole reconciliation

So this file keeps those signatures (plus the ``path_requirements`` property
upstream reads them from) and answers "nothing was installed": ``install_pack``
returns an empty result, which the caller reads as "no dependency was left
behind", and ``cleanup_dist_info`` does nothing. Both log a warning, so a real
update flow never pretends the dependencies of a mod were reconciled.

Replacing this file with the real installer is its own porting item; the
decision is recorded in ``oas/backend/README.md``.
"""

from oas.ext.path import PathStr
from oas.logger import logger


class InstallBase:
    """
    The dependency install of one mod, stubbed to "nothing to install"

    Upstream one instance is one read of the environment: its cached properties
    read the requirements file of the mod, the declared pins and the dependency
    snapshot of its packed tree once and cache the result, which is why the
    caller creates it after the tree of the mod is at the new version. The
    stand-in keeps the same construction contract, so the caller's ordering is
    still correct when the real installer lands.

    Attributes:
        mod (Mod): The mounted mod, its entry carries the requirements file
        site_packages (PathStr): Folder the distributions would be checked in
        client (AsyncClient | AsyncHttpClient | None): Client the pack requests
            would be sent with, owned by the caller and never closed here
    """

    def __init__(self, mod, site_packages, client=None):
        """
        Args:
            mod (Mod): The mounted mod whose requirements file pins the
                dependencies
            site_packages (str | PathStr): Path of the site-packages folder to
                check and install into
            client (httpx2.AsyncClient | AsyncHttpClient, optional): Client the
                pack requests are sent with. Its lifetime belongs to the
                caller, it is never closed here. Defaults to None
        """
        self.mod = mod
        self.site_packages = PathStr.new(site_packages)
        self.client = client

    @property
    def path_requirements(self):
        """
        Path of the requirements file of the mod.

        Returns:
            PathStr: {mod.root}/{entry.requirements_file}
        """
        return self.mod.root.joinpath(self.mod.entry.requirements_file)

    async def install_pack(self) -> 'dict[str, bool]':
        """
        Stand-in of the pack install: install nothing, report nothing failed

        Returns:
            dict[str, bool]: Empty, upstream one entry per dependency name
                saying whether it ended up installed
        """
        logger.warning(
            f'[InstallBase] The dependency installer is not ported yet, '
            f'skipping the pack install of "{getattr(self.mod, "name", self.mod)}"'
        )
        return {}

    async def cleanup_dist_info(self) -> 'list[str]':
        """
        Stand-in of the metadata cleanup after a dependency reconciliation

        Returns:
            list[str]: Empty, upstream the removed metadata directories
        """
        logger.warning(
            f'[InstallBase] The dependency installer is not ported yet, '
            f'skipping the metadata cleanup of "{getattr(self.mod, "name", self.mod)}"'
        )
        return []
