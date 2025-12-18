"""
Qwen MT Langflow Component

This component provides machine translation functionality using Qwen-MT models
via DashScope API. Supports text translation and SRT subtitle file translation.
"""

import os
from pathlib import Path
from typing import Optional

from vibe_surf.langflow.custom import Component
from vibe_surf.langflow.io import MessageTextInput, SecretStrInput, DropdownInput, Output
from vibe_surf.langflow.schema import Data
from vibe_surf.tools.aigc.qwen_mt import QwenMTProcessor
from vibe_surf.langflow.schema.message import Message

# Language mapping: Display name -> Language code
LANGUAGE_MAPPING = {
    "English-英语": "en",
    "Chinese-简体中文": "zh",
    "Traditional Chinese-繁体中文": "zh_tw",
    "Russian-俄语": "ru",
    "Japanese-日语": "ja",
    "Korean-韩语": "ko",
    "Spanish-西班牙语": "es",
    "French-法语": "fr",
    "Portuguese-葡萄牙语": "pt",
    "German-德语": "de",
    "Italian-意大利语": "it",
    "Thai-泰语": "th",
    "Vietnamese-越南语": "vi",
    "Indonesian-印度尼西亚语": "id",
    "Malay-马来语": "ms",
    "Arabic-阿拉伯语": "ar",
    "Hindi-印地语": "hi",
    "Hebrew-希伯来语": "he",
    "Burmese-缅甸语": "my",
    "Tamil-泰米尔语": "ta",
    "Urdu-乌尔都语": "ur",
    "Bengali-孟加拉语": "bn",
    "Polish-波兰语": "pl",
    "Dutch-荷兰语": "nl",
    "Romanian-罗马尼亚语": "ro",
    "Turkish-土耳其语": "tr",
    "Khmer-高棉语": "km",
    "Lao-老挝语": "lo",
    "Cantonese-粤语": "yue",
    "Czech-捷克语": "cs",
    "Greek-希腊语": "el",
    "Swedish-瑞典语": "sv",
    "Hungarian-匈牙利语": "hu",
    "Danish-丹麦语": "da",
    "Finnish-芬兰语": "fi",
    "Ukrainian-乌克兰语": "uk",
    "Bulgarian-保加利亚语": "bg",
    "Serbian-塞尔维亚语": "sr",
    "Telugu-泰卢固语": "te",
    "Afrikaans-南非荷兰语": "af",
    "Armenian-亚美尼亚语": "hy",
    "Assamese-阿萨姆语": "as",
    "Asturian-阿斯图里亚斯语": "ast",
    "Basque-巴斯克语": "eu",
    "Belarusian-白俄罗斯语": "be",
    "Bosnian-波斯尼亚语": "bs",
    "Catalan-加泰罗尼亚语": "ca",
    "Cebuano-宿务语": "ceb",
    "Croatian-克罗地亚语": "hr",
    "Egyptian Arabic-埃及阿拉伯语": "arz",
    "Estonian-爱沙尼亚语": "et",
    "Galician-加利西亚语": "gl",
    "Georgian-格鲁吉亚语": "ka",
    "Gujarati-古吉拉特语": "gu",
    "Icelandic-冰岛语": "is",
    "Javanese-爪哇语": "jv",
    "Kannada-卡纳达语": "kn",
    "Kazakh-哈萨克语": "kk",
    "Latvian-拉脱维亚语": "lv",
    "Lithuanian-立陶宛语": "lt",
    "Luxembourgish-卢森堡语": "lb",
    "Macedonian-马其顿语": "mk",
    "Maithili-马加希语": "mai",
    "Maltese-马耳他语": "mt",
    "Marathi-马拉地语": "mr",
    "Mesopotamian Arabic-美索不达米亚阿拉伯语": "acm",
    "Moroccan Arabic-摩洛哥阿拉伯语": "ary",
    "Najdi Arabic-内志阿拉伯语": "ars",
    "Nepali-尼泊尔语": "ne",
    "North Azerbaijani-北阿塞拜疆语": "az",
    "North Levantine Arabic-北黎凡特阿拉伯语": "apc",
    "Northern Uzbek-北乌兹别克语": "uz",
    "Norwegian Bokmål-书面语挪威语": "nb",
    "Norwegian Nynorsk-新挪威语": "nn",
    "Occitan-奥克语": "oc",
    "Odia-奥里亚语": "or",
    "Pangasinan-邦阿西楠语": "pag",
    "Sicilian-西西里语": "scn",
    "Sindhi-信德语": "sd",
    "Sinhala-僧伽罗语": "si",
    "Slovak-斯洛伐克语": "sk",
    "Slovenian-斯洛文尼亚语": "sl",
    "South Levantine Arabic-南黎凡特阿拉伯语": "ajp",
    "Swahili-斯瓦希里语": "sw",
    "Tagalog-他加禄语": "tl",
    "Ta'izzi-Adeni Arabic-塔伊兹-亚丁阿拉伯语": "acq",
    "Tosk Albanian-托斯克阿尔巴尼亚语": "sq",
    "Tunisian Arabic-突尼斯阿拉伯语": "aeb",
    "Venetian-威尼斯语": "vec",
    "Waray-瓦莱语": "war",
    "Welsh-威尔士语": "cy",
    "Western Persian-西波斯语": "fa",
}


class QwenMTComponent(Component):
    display_name = "Qwen MT"
    description = "Machine Translation using Qwen-MT models. Supports text and SRT subtitle translation."
    icon = "Languages"
    name = "QwenMT"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="DashScope API Key",
            info="The DashScope API Key for Qwen-MT",
            required=True,
        ),
        DropdownInput(
            name="target_language",
            display_name="Target Language",
            info="Target language for translation",
            options=list(LANGUAGE_MAPPING.keys()),
            value="Chinese-简体中文",
            required=True,
        ),
        MessageTextInput(
            name="text",
            display_name="Text to Translate",
            info="Direct text input for translation (if no SRT file provided)",
        ),
        MessageTextInput(
            name="srt_file_path",
            display_name="SRT File Path",
            info="Path to SRT subtitle file for translation (takes priority over text input)",
        ),
        DropdownInput(
            name="model",
            display_name="Model",
            info="Qwen-MT model to use",
            options=["qwen-mt-plus", "qwen-mt-flash", "qwen-mt-turbo", "qwen-mt-lite"],
            value="qwen-mt-plus",
            advanced=True,
        ),
        MessageTextInput(
            name="output_dir",
            display_name="Output Directory",
            info="Optional output directory for translated SRT file (default: same as input file)",
            advanced=True,
        ),
    ]

    outputs = [
        Output(
            name="text_output",
            display_name="Text Output",
            method="translate_content",
        ),
    ]

    def translate_content(self) -> Message:
        """Translate text or SRT file using Qwen-MT"""

        if not self.api_key:
            raise ValueError("DashScope API Key is required")

        if not self.target_language:
            raise ValueError("Target language is required")

        # Map display name to language code
        target_lang_code = LANGUAGE_MAPPING.get(self.target_language, self.target_language)

        # Initialize processor
        processor = QwenMTProcessor(
            dashscope_api_key=self.api_key,
            model=self.model if hasattr(self, 'model') else "qwen-mt-plus"
        )

        # Check if SRT file is provided (priority)
        srt_file = None
        if hasattr(self, 'srt_file_path') and self.srt_file_path:
            srt_file = self.srt_file_path
            if isinstance(srt_file, Data):
                srt_file = srt_file.get_text()

        try:
            if srt_file:
                # Translate SRT file
                resolved_path = self.resolve_path(srt_file)

                # Validate file exists
                if not os.path.exists(resolved_path):
                    raise FileNotFoundError(f"SRT file not found: {resolved_path}")

                # Get output directory if specified
                output_file = None
                if hasattr(self, 'output_dir') and self.output_dir:
                    output_dir = self.output_dir
                    if isinstance(output_dir, Data):
                        output_dir = output_dir.get_text()
                    output_dir = self.resolve_path(output_dir)
                    os.makedirs(output_dir, exist_ok=True)

                    # Construct output file path
                    base_name = os.path.splitext(os.path.basename(resolved_path))[0]
                    output_file = os.path.join(output_dir, f"{base_name}.{target_lang_code}.srt")

                # Translate SRT
                result_path = processor.translate_srt(
                    srt_file=resolved_path,
                    target_language=target_lang_code,
                    output_file=output_file
                )

                self.status = f"✓ SRT translation complete: {result_path}"
                return Message(text=result_path)

            else:
                # Translate direct text
                if not hasattr(self, 'text') or not self.text:
                    raise ValueError("Either text or srt_file_path must be provided")

                text = self.text
                if isinstance(text, Data):
                    text = text.get_text()

                if not text.strip():
                    raise ValueError("Text cannot be empty")

                # Translate text
                translated_text = processor.run(
                    text=text,
                    target_language=target_lang_code
                )

                self.status = f"✓ Text translation complete"
                return Message(text=translated_text)

        except Exception as e:
            self.status = f"✗ Translation failed: {str(e)}"
            raise e
