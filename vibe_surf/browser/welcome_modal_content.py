"""
VibeSurf Welcome Modal Content

Contains the JavaScript code for the welcome modal that appears when
the browser automation starts. Supports multiple languages based on
user's IP location detection.

This module provides:
- EN_WELCOME_JS: English version of the welcome modal
- ZH_WELCOME_JS: Chinese (Simplified) version of the welcome modal
- get_welcome_js(): Returns appropriate JS based on country code
"""

from typing import Optional


def _get_base_welcome_js_template() -> str:
    """
    Returns the base template for welcome modal JavaScript.
    This template contains placeholders that will be filled with
    language-specific content.

    The template includes:
    - CSS styles for the modal
    - Modal structure and animations
    - Event handlers for copy button and close functionality
    - LocalStorage check for dismissed state

    Returns:
        str: Base JavaScript template with {title}, {subtitle}, and other placeholders
    """
    return """
(function showVibeSurfWelcome() {{
    // Check if user has dismissed the welcome modal
    const dismissed = localStorage.getItem('vibesurf_welcome_dismissed');
    if (dismissed === 'true') {{
        console.log('[VibeSurf] Welcome modal was previously dismissed');
        return;
    }}

    // Add styles using createElement to avoid TrustedHTML issues
    const style = document.createElement('style');
    style.textContent = `
        @keyframes fadeIn {{
            from {{ opacity: 0; }}
            to {{ opacity: 1; }}
        }}
        @keyframes slideIn {{
            from {{ transform: translateY(-30px) scale(0.95); opacity: 0; }}
            to {{ transform: translateY(0) scale(1); opacity: 1; }}
        }}
        @keyframes fadeOut {{
            from {{ opacity: 1; }}
            to {{ opacity: 0; }}
        }}
        @keyframes slideOut {{
            from {{ transform: translateY(0) scale(1); opacity: 1; }}
            to {{ transform: translateY(-30px) scale(0.95); opacity: 0; }}
        }}
        @keyframes pulse {{
            0%, 100% {{ transform: scale(1); }}
            50% {{ transform: scale(1.05); }}
        }}
        .vibesurf-title {{
            font-size: 36px;
            font-weight: 800;
            margin: 0 0 12px 0;
            text-align: left;
            letter-spacing: -0.5px;
            line-height: 1.2;
        }}
        .vibesurf-subtitle {{
            font-size: 18px;
            margin: 0 0 32px 0;
            text-align: left;
            opacity: 0.92;
            font-weight: 400;
            line-height: 1.5;
        }}
        .vibesurf-section {{
            background: rgba(111, 233, 255, 0.08);
            border-radius: 16px;
            padding: 24px;
            margin-bottom: 16px;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(111, 233, 255, 0.15);
        }}
        .vibesurf-section-title {{
            font-size: 20px;
            font-weight: 700;
            margin: 0 0 16px 0;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .vibesurf-steps {{
            list-style: none;
            padding: 0;
            margin: 0;
        }}
        .vibesurf-steps li {{
            padding: 10px 0;
            padding-left: 32px;
            position: relative;
            line-height: 1.6;
            font-size: 15px;
        }}
        .vibesurf-steps li:before {{
            content: '✓';
            position: absolute;
            left: 0;
            font-weight: bold;
            color: #6FE9FF;
            font-size: 18px;
            width: 24px;
            height: 24px;
            background: rgba(111, 233, 255, 0.15);
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            line-height: 1;
        }}
        .vibesurf-path-box {{
            background: rgba(0, 0, 0, 0.4);
            border-radius: 10px;
            padding: 14px 16px;
            margin: 12px 0 0 0;
            font-family: 'SF Mono', 'Monaco', 'Courier New', monospace;
            font-size: 13px;
            word-break: break-all;
            display: flex;
            align-items: center;
            gap: 12px;
            border: 1px solid rgba(111, 233, 255, 0.2);
        }}
        .vibesurf-path-text {{
            flex: 1;
            user-select: all;
            color: #6FE9FF;
        }}
        .vibesurf-copy-btn {{
            background: rgba(111, 233, 255, 0.15);
            border: 1px solid rgba(111, 233, 255, 0.3);
            border-radius: 8px;
            padding: 8px 16px;
            color: #6FE9FF;
            cursor: pointer;
            font-size: 13px;
            font-weight: 600;
            transition: all 0.2s ease;
            white-space: nowrap;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
        }}
        .vibesurf-copy-btn:hover {{
            background: rgba(111, 233, 255, 0.25);
            border-color: rgba(111, 233, 255, 0.5);
            transform: translateY(-1px);
            box-shadow: 0 4px 12px rgba(111, 233, 255, 0.4);
        }}
        .vibesurf-copy-btn:active {{
            transform: translateY(0);
        }}
        .vibesurf-warning {{
            background: rgba(255, 193, 7, 0.15);
            border-left: 4px solid #FFC107;
            padding: 18px;
            border-radius: 12px;
            font-size: 14px;
            line-height: 1.7;
            border: 1px solid rgba(255, 193, 7, 0.3);
        }}
        .vibesurf-warning strong {{
            font-size: 15px;
            display: block;
            margin-bottom: 8px;
        }}
        .vibesurf-footer {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-top: 28px;
            padding-top: 24px;
            border-top: 1px solid rgba(255, 255, 255, 0.15);
        }}
        .vibesurf-checkbox-container {{
            display: flex;
            align-items: center;
            gap: 10px;
            cursor: pointer;
            font-size: 15px;
            user-select: none;
        }}
        .vibesurf-checkbox-container input {{
            cursor: pointer;
            width: 20px;
            height: 20px;
            accent-color: #60D394;
        }}
        .vibesurf-btn {{
            background: linear-gradient(135deg, #6FE9FF 0%, #5AD4EB 100%);
            color: #0D2435;
            border: none;
            border-radius: 12px;
            padding: 14px 32px;
            font-size: 16px;
            font-weight: 700;
            cursor: pointer;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            box-shadow: 0 4px 16px rgba(111, 233, 255, 0.3);
            letter-spacing: 0.3px;
        }}
        .vibesurf-btn:hover {{
            background: linear-gradient(135deg, #7FEFFF 0%, #6FE4F5 100%);
            transform: translateY(-2px) scale(1.02);
            box-shadow: 0 8px 24px rgba(111, 233, 255, 0.5);
            animation: pulse 0.6s ease;
        }}
        .vibesurf-btn:active {{
            transform: translateY(0) scale(0.98);
        }}
    `;
    document.head.appendChild(style);

    // Create modal overlay
    const overlay = document.createElement('div');
    overlay.id = 'vibesurf-welcome-overlay';
    overlay.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: rgba(0, 0, 0, 0.7);
        backdrop-filter: blur(5px);
        z-index: 999999;
        display: flex;
        align-items: center;
        justify-content: center;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
        animation: fadeIn 0.3s ease-in;
    `;

    // Create modal container
    const modal = document.createElement('div');
    modal.style.cssText = `
        background: linear-gradient(145deg, #0D2435 0%, #14334A 50%, #1A4059 100%);
        border-radius: 24px;
        padding: 48px;
        max-width: 650px;
        width: 92%;
        box-shadow: 0 24px 80px rgba(26, 64, 89, 0.8), 0 0 0 1px rgba(111, 233, 255, 0.2);
        color: white;
        animation: slideIn 0.5s cubic-bezier(0.34, 1.56, 0.64, 1);
        position: relative;
    `;

    // Create title
    const title = document.createElement('h1');
    title.className = 'vibesurf-title';
    title.textContent = '{title}';
    modal.appendChild(title);

    // Create subtitle
    const subtitle = document.createElement('p');
    subtitle.className = 'vibesurf-subtitle';
    subtitle.textContent = '{subtitle}';
    modal.appendChild(subtitle);

    // Create section 1: How to Enable
    const section1 = document.createElement('div');
    section1.className = 'vibesurf-section';

    const section1Title = document.createElement('h2');
    section1Title.className = 'vibesurf-section-title';
    section1Title.textContent = '{section1_title}';
    section1.appendChild(section1Title);

    const stepsList1 = document.createElement('ul');
    stepsList1.className = 'vibesurf-steps';

    {steps1_list}

    section1.appendChild(stepsList1);
    modal.appendChild(section1);

    // Create warning section
    const warningDiv = document.createElement('div');
    warningDiv.className = 'vibesurf-warning';

    const warningStrong = document.createElement('strong');
    warningStrong.textContent = '{warning_title}';
    warningDiv.appendChild(warningStrong);

    warningDiv.appendChild(document.createTextNode('{warning_text}'));

    const warningSteps = document.createElement('ul');
    warningSteps.className = 'vibesurf-steps';
    warningSteps.style.marginTop = '10px';

    {warning_steps_list}

    // Add path box after step 3
    const pathBox = document.createElement('div');
    pathBox.className = 'vibesurf-path-box';
    pathBox.style.marginTop = '12px';
    pathBox.style.marginLeft = '32px';

    const pathText = document.createElement('span');
    pathText.className = 'vibesurf-path-text';
    pathText.id = 'extension-path';
    pathText.textContent = '{extension_path}';
    pathBox.appendChild(pathText);

    const copyBtn = document.createElement('button');
    copyBtn.className = 'vibesurf-copy-btn';
    copyBtn.id = 'copy-path-btn';
    copyBtn.textContent = '{copy_button_text}';
    pathBox.appendChild(copyBtn);

    warningSteps.appendChild(pathBox);

    warningDiv.appendChild(warningSteps);
    modal.appendChild(warningDiv);

    // Create footer
    const footer = document.createElement('div');
    footer.className = 'vibesurf-footer';

    const checkboxLabel = document.createElement('label');
    checkboxLabel.className = 'vibesurf-checkbox-container';

    const checkbox = document.createElement('input');
    checkbox.type = 'checkbox';
    checkbox.id = 'dont-show-again';
    checkboxLabel.appendChild(checkbox);

    const checkboxText = document.createElement('span');
    checkboxText.textContent = '{checkbox_text}';
    checkboxLabel.appendChild(checkboxText);

    footer.appendChild(checkboxLabel);

    const gotItBtn = document.createElement('button');
    gotItBtn.className = 'vibesurf-btn';
    gotItBtn.id = 'got-it-btn';
    gotItBtn.textContent = '{button_text}';
    footer.appendChild(gotItBtn);

    modal.appendChild(footer);

    // Append to overlay and document
    overlay.appendChild(modal);
    document.body.appendChild(overlay);

    // Copy button functionality
    copyBtn.addEventListener('click', () => {{
        const pathTextContent = document.getElementById('extension-path').textContent;
        navigator.clipboard.writeText(pathTextContent).then(() => {{
            copyBtn.textContent = '{copy_success_text}';
            setTimeout(() => {{
                copyBtn.textContent = '{copy_button_text}';
            }}, 2000);
        }}).catch(err => {{
            console.error('[VibeSurf] Failed to copy:', err);
            copyBtn.textContent = '{copy_error_text}';
            setTimeout(() => {{
                copyBtn.textContent = '{copy_button_text}';
            }}, 2000);
        }});
    }});

    // Close modal function
    function closeModal() {{
        overlay.style.animation = 'fadeOut 0.3s ease-out';
        modal.style.animation = 'slideOut 0.3s ease-out';

        setTimeout(() => {{
            if (document.body.contains(overlay)) {{
                document.body.removeChild(overlay);
            }}
        }}, 300);

        if (checkbox.checked) {{
            localStorage.setItem('vibesurf_welcome_dismissed', 'true');
            console.log('[VibeSurf] Welcome modal dismissed permanently');
        }}
    }}

    // Got It button click handler
    gotItBtn.addEventListener('click', closeModal);

    // Close when clicking outside modal
    overlay.addEventListener('click', (e) => {{
        if (e.target === overlay) {{
            closeModal();
        }}
    }});

    console.log('[VibeSurf] Welcome modal displayed');
}})();
"""


def get_english_welcome_js(extension_path: str) -> str:
    """
    Returns the English version of the welcome modal JavaScript.

    Args:
        extension_path: The file path to the Chrome extension directory

    Returns:
        str: Complete JavaScript code for English welcome modal
    """
    extension_path_js = extension_path.replace('\\', '/')

    steps1_list = """const steps1 = [
        'Click the Extensions icon (puzzle piece) in the top-right corner',
        'Find VibeSurf in the list',
        'Click the Pin icon to keep VibeSurf visible in your toolbar'
    ];

    steps1.forEach(stepText => {{
        const li = document.createElement('li');
        li.textContent = stepText;
        stepsList1.appendChild(li);
    }});"""

    warning_steps_list = """const warningStep1 = document.createElement('li');
    warningStep1.textContent = 'Open chrome://extensions';
    warningSteps.appendChild(warningStep1);

    const warningStep2 = document.createElement('li');
    warningStep2.textContent = 'Enable Developer mode';
    warningSteps.appendChild(warningStep2);

    const warningStep3 = document.createElement('li');
    warningStep3.textContent = 'Click "Load unpacked" and select the following path:';
    warningSteps.appendChild(warningStep3);"""

    template = _get_base_welcome_js_template()
    return template.format(
        title="🎉 Welcome to VibeSurf!",
        subtitle="Your Personal AI Browser Assistant - Let's Vibe Surfing the World!",
        section1_title="📌 How to Enable the Extension",
        steps1_list=steps1_list,
        warning_title="⚠️ Important Note: ",
        warning_text="Since Chrome 142+, extensions must be loaded manually. If you don't see VibeSurf:",
        warning_steps_list=warning_steps_list,
        extension_path=extension_path_js,
        copy_button_text="📋 Copy",
        copy_success_text="✅ Copied!",
        copy_error_text="❌ Failed",
        checkbox_text="Don't show this again",
        button_text="Got It!"
    )


def get_chinese_welcome_js(extension_path: str) -> str:
    """
    Returns the Chinese (Simplified) version of the welcome modal JavaScript.

    Args:
        extension_path: The file path to the Chrome extension directory

    Returns:
        str: Complete JavaScript code for Chinese welcome modal
    """
    extension_path_js = extension_path.replace('\\', '/')

    steps1_list = """const steps1 = [
        '点击右上角的扩展程序图标（拼图图标）',
        '在列表中找到 VibeSurf',
        '点击图钉图标将 VibeSurf 固定到工具栏'
    ];

    steps1.forEach(stepText => {{
        const li = document.createElement('li');
        li.textContent = stepText;
        stepsList1.appendChild(li);
    }});"""

    warning_steps_list = """const warningStep1 = document.createElement('li');
    warningStep1.textContent = '打开 chrome://extensions';
    warningSteps.appendChild(warningStep1);

    const warningStep2 = document.createElement('li');
    warningStep2.textContent = '开启开发者模式';
    warningSteps.appendChild(warningStep2);

    const warningStep3 = document.createElement('li');
    warningStep3.textContent = '点击"加载已解压的扩展程序"并选择以下路径：';
    warningSteps.appendChild(warningStep3);"""

    template = _get_base_welcome_js_template()
    return template.format(
        title="🎉 欢迎来到 VibeSurf！",
        subtitle="您的个人 AI 浏览器助手 - 一起冲浪世界吧！",
        section1_title="📌 如何启用扩展程序",
        steps1_list=steps1_list,
        warning_title="⚠️ 重要提示：",
        warning_text="自 Chrome 142+ 版本起，扩展程序必须手动加载。如果您没有看到 VibeSurf：",
        warning_steps_list=warning_steps_list,
        extension_path=extension_path_js,
        copy_button_text="📋 复制",
        copy_success_text="✅ 已复制！",
        copy_error_text="❌ 复制失败",
        checkbox_text="不再显示此提示",
        button_text="知道了！"
    )


async def get_welcome_js(country_code: Optional[str] = None, extension_path: str = "") -> str:
    """
    Get the appropriate welcome modal JavaScript based on country code.

    This function uses the user's IP location to determine which language
    version of the welcome modal to display. Users from China will see the
    Chinese version, while all other users will see the English version.

    Args:
        country_code: ISO 3166-1 alpha-2 country code (e.g., 'CN', 'US', 'JP').
                     If None, will attempt to detect from IP. Defaults to None.
        extension_path: The file path to the Chrome extension directory.

    Returns:
        str: JavaScript code for the welcome modal in the appropriate language

    Examples:
        >>> await get_welcome_js('CN', '/path/to/extension')
        # Returns Chinese welcome modal

        >>> await get_welcome_js('US', '/path/to/extension')
        # Returns English welcome modal

        >>> await get_welcome_js(None, '/path/to/extension')
        # Attempts IP detection, defaults to English if detection fails
    """
    # Import here to avoid circular dependency
    import httpx
    import logging

    logger = logging.getLogger(__name__)

    # If country code not provided, try to detect from IP
    if country_code is None:
        try:
            async with httpx.AsyncClient(trust_env=False) as client:
                response = await client.get("http://ipinfo.io/json", timeout=2.0)
                if response.status_code == 200:
                    ip_data = response.json()
                    country_code = ip_data.get("country", "US")
                    logger.info(f"[WelcomeModal] Detected country from IP: {country_code}")
                else:
                    country_code = "US"
        except (httpx.TimeoutException, httpx.RequestError, ValueError) as e:
            logger.warning(f"[WelcomeModal] Error detecting IP location (using default): {e}")
            country_code = "US"

    # Select language based on country code
    # China (CN) uses Chinese, all others use English
    if country_code == "CN":
        logger.info("[WelcomeModal] Using Chinese welcome modal")
        return get_chinese_welcome_js(extension_path)
    else:
        logger.info("[WelcomeModal] Using English welcome modal")
        return get_english_welcome_js(extension_path)


# Convenience functions for direct access
def get_welcome_js_en(extension_path: str) -> str:
    """
    Convenience function to get English welcome modal without IP detection.

    Args:
        extension_path: The file path to the Chrome extension directory

    Returns:
        str: English welcome modal JavaScript
    """
    return get_english_welcome_js(extension_path)


def get_welcome_js_zh(extension_path: str) -> str:
    """
    Convenience function to get Chinese welcome modal without IP detection.

    Args:
        extension_path: The file path to the Chrome extension directory

    Returns:
        str: Chinese welcome modal JavaScript
    """
    return get_chinese_welcome_js(extension_path)
