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

    def get_args(self) -> list[str]:
        """Get the list of all Chrome CLI launch args for this profile (compiled from defaults, user-provided, and system-specific)."""

        if isinstance(self.ignore_default_args, list):
            default_args = set(CHROME_DEFAULT_ARGS) - set(self.ignore_default_args)
        elif self.ignore_default_args is True:
            default_args = []
        elif not self.ignore_default_args:
            default_args = CHROME_DEFAULT_ARGS

        # Filter out microphone-blocking arguments for voice functionality
        default_args = self._filter_microphone_blocking_args(default_args)
        assert self.user_data_dir is not None, 'user_data_dir must be set to a non-default path'

        # Capture args before conversion for logging
        pre_conversion_args = [
            *default_args,
            *self.args,
            f'--user-data-dir={self.user_data_dir}',
            f'--profile-directory={self.profile_directory}',
            *(CHROME_DOCKER_ARGS if (CONFIG.IN_DOCKER or not self.chromium_sandbox) else []),
            *(CHROME_HEADLESS_ARGS if self.headless else []),
            *(CHROME_DISABLE_SECURITY_ARGS if self.disable_security else []),
            *(CHROME_DETERMINISTIC_RENDERING_ARGS if self.deterministic_rendering else []),
            *(
                [f'--window-size={self.window_size["width"]},{self.window_size["height"]}']
                if self.window_size
                else (['--start-maximized'] if not self.headless else [])
            ),
            *(
                [f'--window-position={self.window_position["width"]},{self.window_position["height"]}']
                if self.window_position
                else []
            ),
            *(self._get_extension_args() if self.enable_default_extensions else []),
        ]

        # Proxy flags
        proxy_server = self.proxy.server if self.proxy else None
        proxy_bypass = self.proxy.bypass if self.proxy else None

        if proxy_server:
            pre_conversion_args.append(f'--proxy-server={proxy_server}')
            if proxy_bypass:
                pre_conversion_args.append(f'--proxy-bypass-list={proxy_bypass}')

        # User agent flag
        if self.user_agent:
            pre_conversion_args.append(f'--user-agent={self.user_agent}')

        # Special handling for --disable-features to merge values instead of overwriting
        # This prevents disable_security=True from breaking extensions by ensuring
        # both default features (including extension-related) and security features are preserved
        disable_features_values = []
        non_disable_features_args = []

        # Extract and merge all --disable-features values
        for arg in pre_conversion_args:
            if arg.startswith('--disable-features='):
                features = arg.split('=', 1)[1]
                disable_features_values.extend(features.split(','))
            else:
                non_disable_features_args.append(arg)

        # Remove duplicates while preserving order
        if disable_features_values:
            unique_features = []
            seen = set()
            for feature in disable_features_values:
                feature = feature.strip()
                if feature and feature not in seen:
                    unique_features.append(feature)
                    seen.add(feature)

            # Add merged disable-features back
            non_disable_features_args.append(f'--disable-features={",".join(unique_features)}')

        # convert to dict and back to dedupe and merge other duplicate args
        final_args_list = BrowserLaunchArgs.args_as_list(BrowserLaunchArgs.args_as_dict(non_disable_features_args))

        return final_args_list

    def _get_extension_args(self) -> list[str]:
        """Get Chrome args for enabling default extensions (ad blocker and cookie handler)."""
        extension_paths = self._ensure_default_extensions_downloaded()

        args = [
            '--enable-extensions',
            '--disable-extensions-file-access-check',
            '--disable-extensions-http-throttling',
            '--enable-extension-activity-logging',
        ]

        if extension_paths:
            args.append(f'--load-extension={",".join(extension_paths)}')

        return args

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

    def _filter_microphone_blocking_args(self, args: set[str]) -> set[str]:
        """Filter out arguments that block microphone functionality for voice input."""
        filtered_args = set()
        
        for arg in args:
            # Skip speech-related blocking arguments
            if arg in ['--disable-speech-synthesis-api', '--disable-speech-api']:
                logger.info(f'[BrowserProfile] 🎤 Skipping microphone-blocking arg: {arg}')
                continue
                
            # Handle --disable-features arguments
            if arg.startswith('--disable-features='):
                features = arg.split('=', 1)[1]
                feature_list = features.split(',')
                
                # Remove microphone-blocking features
                filtered_features = []
                for feature in feature_list:
                    feature = feature.strip()
                    if feature in ['GlobalMediaControls', 'MediaRouter']:
                        logger.info(f'[BrowserProfile] 🎤 Removing microphone-blocking feature: {feature}')
                        continue
                    filtered_features.append(feature)
                
                if filtered_features:
                    filtered_args.add(f'--disable-features={",".join(filtered_features)}')
                continue
            
            # Keep all other arguments
            filtered_args.add(arg)
        
        logger.info(f'[BrowserProfile] 🎤 Filtered {len(args) - len(filtered_args)} microphone-blocking arguments')
        return filtered_args

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
