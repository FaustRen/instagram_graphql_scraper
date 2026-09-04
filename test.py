#%%

import json
import requests

url = "https://www.instagram.com/api/graphql"

# ==========================================
# Payload
# Content-Type: application/x-www-form-urlencoded
# ==========================================

payload = {
    "av": "0",
    "__d": "www",
    "__user": "0",
    "__a": "1",
    "__req": "h",
    "__hs": "20697.HYP:instagram_web_pkg.2.1...0",
    "dpr": "2",
    "__ccg": "EXCELLENT",
    "__rev": "1046506236",
    "__s": "f1k8u0:m06850:s3ve4l",
    "__hsi": "7680648101288692485",

    "__dyn": (
        "7xeUjG1mxu1syaxG4Vp41twpUnwgU7SbzEdF8vyUco2qwJyE1kUhw2nVE4"
        "W0qa321Rw8G11wBz81s8hwGxu786a3a1YwBgao6C1uwoE2swlo8od8-U2z"
        "xe2GewGw9a361qw8Xxm16wa-0oa2-azo7u3C2u2J0bS1LyUaUbGxK3R08-"
        "269wr84-6o5p389oed6goK10xKi2K7E5y4U158KmUhw4rwXyEcFE461Hwj"
        "83KwRzk1jw"
    ),

    "__csr": (
        "gcsn2cAWsgCAxkYApMRRmAygLVG9kDazlQp_qGKQAh9X-p8OmgOYQJfm"
        "DrAN2ZT8V9pWRsigD7kBqFHim-GFEAW8GblOkBmjdpVpFv9GiiQymqiKuSQ"
        "8EB4qWjAIFqhipES2SjdBG9z6Xheh5JoiKfxiGxG49FU8oK7XxOmUgUyGgj"
        "xy8BWGEmzVpUSQK4Z2EBfyAK8yEy68qKqbwwDAyrBGq8zk9xWmXyUObxpG"
        "bx6dwXwywWwDK8gcAUG1bBy42u2bAzEnwBw096m00Qmoeo0tqwJg1CFDw1"
        "uW05uU1BFU7Jw2e8Wph2xd1rS0om0vXaEjgmQu8wIy8x0UDwtA7i0Lye1i"
        "w860dxDg-i03BW026e037Wu8gb81J9ik0lW11U0mxw1hS"
    ),

    "__hsdp": (
        "giE2F7QPgP2Iy8kbO9XBVlggucDiCzpojUwygO3jA4qxQg6FNGgaSbxaUt"
        "g5C3wwcXg2787UF1G2KfkC224K1Hz8fEfUuwat1O3e2K9By8aE5y1TwOwl"
        "85e1gxG2e78W0LWxiU5mi0qC0F81s80sewfi08Vxu0cIw8S3-3e0C20HBw"
        "Ww2Yobo15K1Fw6jwi80Ou0oS0nK260w83rCFQ0-S"
    ),

    "__hblp": (
        "0i85q10wp89u48G3vwm8-2KdyVHz-m1oU8Gh8jKfxW1hwg8vym6ErzUnww"
        "ghVUG59Qm3icw-w_xW1NyqwEgTz8txmEa8Cm8wGwm872qm3W12wkUO13xG"
        "2e78W0KF5wCyUy2idAAyElwfS0xo2AwWU560Uoiw5BwoUfU4W10w3Qo4a3"
        "Ofwfi08Vxu0bww8S1bw_xq5Fob-261482J4DwOw9209wwJw9-1SU6Cdw65"
        "wi80Ou0O82hwOz983CwYwho8p86a68co2FCFQ0-S"
    ),

    "__sjsp": (
        "giE2F4jkPhQl2Iy8kbRCKnBl11a7USm4-88A19wiFNGgaUS4E0n2w0jTE"
    ),

    "__comet_req": "7",

    # 注意：這裡使用你「文字 payload」裡的值
    "lsd": "AdRwLWKQzJ2E6nsbCGfOTcTW04Y",

    "jazoest": "22239",

    "__spin_r": "1046506236",
    "__spin_b": "trunk",
    "__spin_t": "1788290241",

    "__crn": "comet.igweb.PolarisLoggedOutDesktopWWWProfileRoute",

    "fb_api_caller_class": "RelayModern",

    "fb_api_req_friendly_name": (
        "PolarisLoggedOutDesktopWWWProfilePostsTabContentQuery_connection"
    ),

    "server_timestamps": "true",

    # 這個欄位本身要是 JSON string，不是 Python dict
    "variables": json.dumps(
        {
            "after": (
                ## new test case: before init
                
                "AQHTtTk_hoxi16i2LcPIFYUtFCGtfTBoC2hwu_Jgpr4Rek6KmNc5SyQAOA9EMIJjH-PC6qbCGOg6jVV22Irw61zFcg"
                
                ### old test
                # "AQHTnz6fALxt3GEUA1r0Xk9kfctgYk_ui7Vqn2UIMzk44TC0F_WHimchPAG5UCGRqlpbs7sJg42Ki4A24yVsglA0Qg"
                # "AQHTEbwmXFwty4uFmXB3SL2qXepXvYUI22oVVSANnPZimxjjwJK2Uo5GTqFnUL581RMDaPYUbFuNx2dIpN-AInejuw"
                # "AQHT_6F4cZFOHc4Y5voR6sqjPzbUxnTY3o7xchcBy_"
                # "AC77eFySK0XSDrDj6B-Ije9OvdG2Js8F1McfpCGhbwoLoMnw"
            ),
            
            "first": 12,
            "id": "17841400543635796",
        },
        separators=(",", ":"),
    ),

    "doc_id": "27389614800735091",
}

headers = {
    "accept": "*/*",
    "accept-language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",

    "content-type": "application/x-www-form-urlencoded",

    "origin": "https://www.instagram.com",
    "referer": "https://www.instagram.com/1989ivyshao",

    "sec-ch-prefers-color-scheme": "dark",
    "sec-ch-ua": (
        '"Chromium";v="152", '
        '"Not?A_Brand";v="24", '
        '"Google Chrome";v="152"'
    ),
    "sec-ch-ua-full-version-list": (
        '"Chromium";v="152.0.7977.65", '
        '"Not?A_Brand";v="24.0.0.0", '
        '"Google Chrome";v="152.0.7977.65"'
    ),
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-model": '""',
    "sec-ch-ua-platform": '"macOS"',
    "sec-ch-ua-platform-version": '"15.0.1"',

    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",

    "user-agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/152.0.0.0 Safari/537.36"
    ),

    "x-asbd-id": "359341",

    "x-csrftoken": "HmUNsXJ5SH63aELKLyY7T0",

    "x-fb-friendly-name": (
        "PolarisLoggedOutDesktopWWWProfilePostsTabContentQuery_connection"
    ),

    # 先注意這裡，下面我會解釋
    "x-fb-lsd": "AdRwLWKQzJ2E6nsbCGfOTcTW04Y",

    "x-ig-app-id": "936619743392459",

    "x-ig-max-touch-points": "0",
}


response = requests.post(url, data=payload, headers=headers)
print(response.status_code)
# %%
response.text
# %%


#%%
json_data = json.loads(response.text)
# json_data.keys()
print(json_data['data']['node']['page_info']['end_cursor'])

# %%
