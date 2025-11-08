import hashlib
import random
import time
import json
import re
import urllib.parse
from typing import Dict, List, Tuple, Optional


def generate_trace_id() -> str:
    """Generate a random trace ID for requests"""
    chars = "abcdef0123456789"
    return ''.join(random.choices(chars, k=16))


def create_session_id() -> str:
    """Create a unique session identifier"""
    timestamp = int(time.time() * 1000) << 64
    rand_num = random.randint(0, 2147483646)
    return encode_base36(timestamp + rand_num)


def encode_base36(number: int, alphabet: str = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ') -> str:
    """Convert integer to base36 string"""
    if not isinstance(number, int):
        raise TypeError('Input must be an integer')

    if number == 0:
        return alphabet[0]

    result = ''
    sign = ''

    if number < 0:
        sign = '-'
        number = -number

    while number:
        number, remainder = divmod(number, len(alphabet))
        result = alphabet[remainder] + result

    return sign + result


def decode_base36(encoded: str) -> int:
    """Decode base36 string to integer"""
    return int(encoded, 36)


def compute_hash(data: str) -> int:
    """Compute hash for given data string"""
    hash_table = [
        0, 1996959894, 3993919788, 2567524794, 124634137, 1886057615, 3915621685,
        2657392035, 249268274, 2044508324, 3772115230, 2547177864, 162941995,
        2125561021, 3887607047, 2428444049, 498536548, 1789927666, 4089016648,
        2227061214, 450548861, 1843258603, 4107580753, 2211677639, 325883990,
        1684777152, 4251122042, 2321926636, 335633487, 1661365465, 4195302755,
        2366115317, 997073096, 1281953886, 3579855332, 2724688242, 1006888145,
        1258607687, 3524101629, 2768942443, 901097722, 1119000684, 3686517206,
        2898065728, 853044451, 1172266101, 3705015759, 2882616665, 651767980,
        1373503546, 3369554304, 3218104598, 565507253, 1454621731, 3485111705,
        3099436303, 671266974, 1594198024, 3322730930, 2970347812, 795835527,
        1483230225, 3244367275, 3060149565, 1994146192, 31158534, 2563907772,
        4023717930, 1907459465, 112637215, 2680153253, 3904427059, 2013776290,
        251722036, 2517215374, 3775830040, 2137656763, 141376813, 2439277719,
        3865271297, 1802195444, 476864866, 2238001368, 4066508878, 1812370925,
        453092731, 2181625025, 4111451223, 1706088902, 314042704, 2344532202,
        4240017532, 1658658271, 366619977, 2362670323, 4224994405, 1303535960,
        984961486, 2747007092, 3569037538, 1256170817, 1037604311, 2765210733,
        3554079995, 1131014506, 879679996, 2909243462, 3663771856, 1141124467,
        855842277, 2852801631, 3708648649, 1342533948, 654459306, 3188396048,
        3373015174, 1466479909, 544179635, 3110523913, 3462522015, 1591671054,
        702138776, 2966460450, 3352799412, 1504918807, 783551873, 3082640443,
        3233442989, 3988292384, 2596254646, 62317068, 1957810842, 3939845945,
        2647816111, 81470997, 1943803523, 3814918930, 2489596804, 225274430,
        2053790376, 3826175755, 2466906013, 167816743, 2097651377, 4027552580,
        2265490386, 503444072, 1762050814, 4150417245, 2154129355, 426522225,
        1852507879, 4275313526, 2312317920, 282753626, 1742555852, 4189708143,
        2394877945, 397917763, 1622183637, 3604390888, 2714866558, 953729732,
        1340076626, 3518719985, 2797360999, 1068828381, 1219638859, 3624741850,
        2936675148, 906185462, 1090812512, 3747672003, 2825379669, 829329135,
        1181335161, 3412177804, 3160834842, 628085408, 1382605366, 3423369109,
        3138078467, 570562233, 1426400815, 3317316542, 2998733608, 733239954,
        1555261956, 3268935591, 3050360625, 752459403, 1541320221, 2607071920,
        3965973030, 1969922972, 40735498, 2617837225, 3943577151, 1913087877,
        83908371, 2512341634, 3803740692, 2075208622, 213261112, 2463272603,
        3855990285, 2094854071, 198958881, 2262029012, 4057260610, 1759359992,
        534414190, 2176718541, 4139329115, 1873836001, 414664567, 2282248934,
        4279200368, 1711684554, 285281116, 2405801727, 4167216745, 1634467795,
        376229701, 2685067896, 3608007406, 1308918612, 956543938, 2808555105,
        3495958263, 1231636301, 1047427035, 2932959818, 3654703836, 1088359270,
        936918000, 2847714899, 3736837829, 1202900863, 817233897, 3183342108,
        3401237130, 1404277552, 615818150, 3134207493, 3453421203, 1423857449,
        601450431, 3009837614, 3294710456, 1567103746, 711928724, 3020668471,
        3272380065, 1510334235, 755167117,
    ]

    hash_val = -1
    for i in range(min(57, len(data))):
        hash_val = hash_table[(hash_val & 255) ^ ord(data[i])] ^ (hash_val >> 8)

    return hash_val ^ -1 ^ 3988292384


# Custom base64 implementation
ENCODING_CHARS = [
    "Z", "m", "s", "e", "r", "b", "B", "o", "H", "Q", "t", "N", "P", "+", "w", "O",
    "c", "z", "a", "/", "L", "p", "n", "g", "G", "8", "y", "J", "q", "4", "2", "K",
    "W", "Y", "j", "0", "D", "S", "f", "d", "i", "k", "x", "3", "V", "T", "1", "6",
    "I", "l", "U", "A", "F", "M", "9", "7", "h", "E", "C", "v", "u", "R", "X", "5",
]


def encode_triplet(triplet: int) -> str:
    """Encode 3-byte triplet to 4-character string"""
    return (
            ENCODING_CHARS[63 & (triplet >> 18)] +
            ENCODING_CHARS[63 & (triplet >> 12)] +
            ENCODING_CHARS[(triplet >> 6) & 63] +
            ENCODING_CHARS[triplet & 63]
    )


def encode_chunk(data: List[int], start: int, end: int) -> str:
    """Encode chunk of bytes"""
    result = []
    for i in range(start, end, 3):
        triplet = (data[i] << 16) | (data[i + 1] << 8) | data[i + 2]
        result.append(encode_triplet(triplet))
    return ''.join(result)


def custom_base64_encode(data: List[int]) -> str:
    """Custom base64 encoding"""
    length = len(data)
    remainder = length % 3
    chunks = []
    chunk_size = 16383

    main_length = length - remainder
    offset = 0

    while offset < main_length:
        end = min(offset + chunk_size, main_length)
        chunks.append(encode_chunk(data, offset, end))
        offset += chunk_size

    if remainder == 1:
        last_byte = data[length - 1]
        chunks.append(
            ENCODING_CHARS[last_byte >> 2] +
            ENCODING_CHARS[(last_byte << 4) & 63] +
            "=="
        )
    elif remainder == 2:
        last_two = (data[length - 2] << 8) | data[length - 1]
        chunks.append(
            ENCODING_CHARS[last_two >> 10] +
            ENCODING_CHARS[(last_two >> 4) & 63] +
            ENCODING_CHARS[(last_two << 2) & 63] +
            "="
        )

    return "".join(chunks)


def utf8_encode(text: str) -> List[int]:
    """Encode text to UTF-8 byte array"""
    encoded_text = urllib.parse.quote(text, safe='~()*!.\'')
    bytes_array = []
    i = 0

    while i < len(encoded_text):
        char = encoded_text[i]
        if char == "%":
            hex_code = encoded_text[i + 1:i + 3]
            byte_val = int(hex_code, 16)
            bytes_array.append(byte_val)
            i += 3
        else:
            bytes_array.append(ord(char))
            i += 1

    return bytes_array


def create_signature_headers(a1: str = "", b1: str = "", x_s: str = "", x_t: str = "") -> Dict[str, str]:
    """Create signature headers for API requests"""
    common_data = {
        "s0": 3,
        "s1": "",
        "x0": "1",
        "x1": "4.2.2",
        "x2": "Mac OS",
        "x3": "xhs-pc-web",
        "x4": "4.74.0",
        "x5": a1,
        "x6": x_t,
        "x7": x_s,
        "x8": b1,
        "x9": compute_hash(x_t + x_s + b1),
        "x10": 154,
        "x11": "normal"
    }

    json_data = json.dumps(common_data, separators=(',', ':'))
    encoded_bytes = utf8_encode(json_data)
    x_s_common = custom_base64_encode(encoded_bytes)
    trace_id = generate_trace_id()

    return {
        "x-s": x_s,
        "x-t": x_t,
        "x-s-common": x_s_common,
        "x-b3-traceid": trace_id
    }


def extract_cookies_from_browser(web_cookies: List[Dict]) -> Tuple[str, Dict[str, str]]:
    """Extract and format cookies from browser, filtering only XiaoHongShu related cookies"""
    cookie_dict = {}
    cookie_parts = []

    # XiaoHongShu domain patterns to filter
    xhs_domains = [
        '.xiaohongshu.com',
        'www.xiaohongshu.com',
        'edith.xiaohongshu.com'
    ]

    for cookie in web_cookies:
        if 'name' in cookie and 'value' in cookie and 'domain' in cookie:
            domain = cookie['domain']

            # Filter only XiaoHongShu related cookies
            if any(xhs_domain in domain for xhs_domain in xhs_domains):
                name = cookie['name']
                value = cookie['value']
                cookie_dict[name] = value
                cookie_parts.append(f"{name}={value}")

    cookie_string = "; ".join(cookie_parts)
    return cookie_string, cookie_dict


# Image CDN configurations
IMAGE_CDNS = [
    "https://sns-img-qc.xhscdn.com",
    "https://sns-img-hw.xhscdn.com",
    "https://sns-img-bd.xhscdn.com",
    "https://sns-img-qn.xhscdn.com",
]


def get_image_url(trace_id: str, image_format: str = "png") -> str:
    """Get image URL from trace ID"""
    cdn = random.choice(IMAGE_CDNS)
    return f"{cdn}/{trace_id}?imageView2/format/{image_format}"


def get_all_image_urls(trace_id: str, image_format: str = "png") -> List[str]:
    """Get all image URLs from different CDNs"""
    return [f"{cdn}/{trace_id}?imageView2/format/{image_format}" for cdn in IMAGE_CDNS]


def extract_trace_id_from_url(image_url: str) -> str:
    """Extract trace ID from image URL"""
    if "spectrum" in image_url:
        return f"spectrum/{image_url.split('/')[-1]}"
    return image_url.split("/")[-1]


def extract_user_info_from_html(html: str) -> Optional[Dict]:
    match = re.search(
        r"<script>window.__INITIAL_STATE__=(.+)<\/script>", html, re.M
    )
    if match is None:
        return None
    info = json.loads(match.group(1).replace(":undefined", ":null"), strict=False)
    if info is None:
        return None
    return info.get("user").get("userPageData")


class XHSError(Exception):
    """Base exception for XHS API errors"""
    pass


class NetworkError(XHSError):
    """Network connection error"""
    pass


class DataExtractionError(XHSError):
    """Data extraction error"""
    pass


class AuthenticationError(XHSError):
    """Authentication error"""
    pass
