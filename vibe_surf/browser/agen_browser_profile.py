import pdb
import sys
import tempfile
from collections.abc import Iterable
from enum import Enum
from functools import cache
from pathlib import Path
from re import Pattern
from typing import Annotated, Any, Literal, Self
from urllib.parse import urlparse

from pydantic import AfterValidator, AliasChoices, BaseModel, ConfigDict, Field, field_validator, model_validator
from uuid_extensions import uuid7str

from browser_use.config import CONFIG
from browser_use.observability import observe_debug
from browser_use.utils import _log_pretty_path, logger

from browser_use.browser import BrowserProfile
from browser_use.browser.profile import CHROME_DEFAULT_ARGS, CHROME_DOCKER_ARGS, CHROME_HEADLESS_ARGS, \
    CHROME_DETERMINISTIC_RENDERING_ARGS, CHROME_DISABLE_SECURITY_ARGS, BrowserLaunchArgs


class AgentBrowserProfile(BrowserProfile):
    custom_extensions: list[str] | None = Field(
        default=None,
        description="Enable Custom Extensions.",
    )

    def _ensure_default_extensions_downloaded(self) -> list[str]:
        """
        Ensure default extensions are downloaded and cached locally.
        Returns list of paths to extension directories.
        """

        # Extension definitions - optimized for automation and content extraction
        extensions = [
            # {
            #     'name': 'uBlock Origin',
            #     'id': 'cjpalhdlnbpafiamejdnhcphjbkeiagm',
            #     'url': 'https://clients2.google.com/service/update2/crx?response=redirect&prodversion=130&acceptformat=crx3&x=id%3Dcjpalhdlnbpafiamejdnhcphjbkeiagm%26uc',
            # },
            {
                'name': "I still don't care about cookies",
                'id': 'edibdbjcniadpccecjdfdjjppcpchdlm',
                'url': 'https://clients2.google.com/service/update2/crx?response=redirect&prodversion=130&acceptformat=crx3&x=id%3Dedibdbjcniadpccecjdfdjjppcpchdlm%26uc',
            },
            # {
            #     'name': 'Force Background Tab',
            #     'id': 'gidlfommnbibbmegmgajdbikelkdcmcl',
            #     'url': 'https://clients2.google.com/service/update2/crx?response=redirect&prodversion=133&acceptformat=crx3&x=id%3Dgidlfommnbibbmegmgajdbikelkdcmcl%26uc',
            # },
            # {
            #     'name': 'ClearURLs',
            #     'id': 'lckanjgmijmafbedllaakclkaicjfmnk',
            #     'url': 'https://clients2.google.com/service/update2/crx?response=redirect&prodversion=130&acceptformat=crx3&x=id%3Dlckanjgmijmafbedllaakclkaicjfmnk%26uc',
            # },
            # {
            # 	'name': 'Captcha Solver: Auto captcha solving service',
            # 	'id': 'pgojnojmmhpofjgdmaebadhbocahppod',
            # 	'url': 'https://clients2.google.com/service/update2/crx?response=redirect&prodversion=130&acceptformat=crx3&x=id%3Dpgojnojmmhpofjgdmaebadhbocahppod%26uc',
            # },
            # {
            # 	'name': 'Consent-O-Matic',
            # 	'id': 'mdjildafknihdffpkfmmpnpoiajfjnjd',
            # 	'url': 'https://clients2.google.com/service/update2/crx?response=redirect&prodversion=130&acceptformat=crx3&x=id%3Dmdjildafknihdffpkfmmpnpoiajfjnjd%26uc',
            # },
            # {
            # 	'name': 'Privacy | Protect Your Payments',
            # 	'id': 'hmgpakheknboplhmlicfkkgjipfabmhp',
            # 	'url': 'https://clients2.google.com/service/update2/crx?response=redirect&prodversion=130&acceptformat=crx3&x=id%3Dhmgpakheknboplhmlicfkkgjipfabmhp%26uc',
            # },
        ]

        # Create extensions cache directory
        cache_dir = CONFIG.BROWSER_USE_EXTENSIONS_DIR
        cache_dir.mkdir(parents=True, exist_ok=True)
        # logger.debug(f'📁 Extensions cache directory: {_log_pretty_path(cache_dir)}')

        extension_paths = []
        loaded_extension_names = []

        for ext in extensions:
            ext_dir = cache_dir / ext['id']
            crx_file = cache_dir / f'{ext["id"]}.crx'

            # Check if extension is already extracted
            if ext_dir.exists() and (ext_dir / 'manifest.json').exists():
                # logger.debug(f'✅ Using cached {ext["name"]} extension from {_log_pretty_path(ext_dir)}')
                extension_paths.append(str(ext_dir))
                loaded_extension_names.append(ext['name'])
                continue

            try:
                # Download extension if not cached
                if not crx_file.exists():
                    logger.info(f'📦 Downloading {ext["name"]} extension...')
                    self._download_extension(ext['url'], crx_file)
                else:
                    logger.debug(f'📦 Found cached {ext["name"]} .crx file')

                # Extract extension
                logger.info(f'📂 Extracting {ext["name"]} extension...')
                self._extract_extension(crx_file, ext_dir)
                extension_paths.append(str(ext_dir))
                loaded_extension_names.append(ext['name'])

            except Exception as e:
                logger.warning(f'⚠️ Failed to setup {ext["name"]} extension: {e}')
                continue

        if extension_paths:
            logger.debug(
                f'[BrowserProfile] 🧩 Extensions loaded ({len(extension_paths)}): [{", ".join(loaded_extension_names)}]')
        else:
            logger.warning('[BrowserProfile] ⚠️ No default extensions could be loaded')

        return extension_paths

    def _get_extension_args(self) -> list[str]:
        """Get Chrome args for enabling default extensions (ad blocker and cookie handler)."""
        extension_paths = self._ensure_default_extensions_downloaded()

        args = [
            '--enable-extensions',
            '--disable-extensions-file-access-check',
            '--disable-extensions-http-throttling',
            '--enable-extension-activity-logging',
            '--disable-features=DisableLoadExtensionCommandLineSwitch'
        ]
        if self.custom_extensions:
            extension_paths.extend(self.custom_extensions)
        if extension_paths:
            args.append(f'--load-extension={",".join(extension_paths)}')
        logger.info(f"Extension infos: {args}")
        return args
