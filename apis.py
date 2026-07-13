# To run this code you need to install the following dependencies:
# pip install google-genai

import base64
import os
from google import genai
from google.genai import types


def generate(data,lang):
    client = genai.Client(
        api_key=os.getenv("GEMINI_API_KEY", "AIzaSyBwUWCGI0z54hn0oylWRcFhtlVnTg58uZ0"),
    )

    model = "gemini-2.0-flash"
    contents = [
        types.Content(
            role="user",
            parts=[
                types.Part.from_text(text=f"""Translate to {lang}: {data}"""),
            ],
        ),
    ]
    tools = [
        types.Tool(googleSearch=types.GoogleSearch(
        )),
    ]
    generate_content_config = types.GenerateContentConfig(
        tools=tools,
        system_instruction=[
            types.Part.from_text(text="""Your are a translator need to frame a json as meaningfull sentence like speaking and then need to translate. You need to only reply for the translation of the given text. No other extra replies."""),
        ],
    )

    for chunk in client.models.generate_content_stream(
        model=model,
        contents=contents,
        config=generate_content_config,
    ):
        print(chunk.text, end="")

# import requests

# url = "https://irctc-api2.p.rapidapi.com/trainSchedule"

# querystring = {"trainNumber":"12321"}

# headers = {
# 	"x-rapidapi-key": "2fb9ba1e2fmsh08e12f01e8df0eap1d6d1ajsna43768b25d57",
# 	"x-rapidapi-host": "irctc-api2.p.rapidapi.com"
# }

# response = requests.get(url, headers=headers, params=querystring)
# print(response.json())

# if __name__ == "__main__":
#     generate(response.json(),"english")


import requests

url = "https://irctc1.p.rapidapi.com/api/v1/liveTrainStatus"

querystring = {"trainNo":"22638","startDay":"1"}

headers = {
	"x-rapidapi-key": "80fa9b5699mshe0309437f11cce3p16566ejsnd4da58c458d9",
	"x-rapidapi-host": "irctc1.p.rapidapi.com"
}

response = requests.get(url, headers=headers, params=querystring)

print(response.json())
with open("trainStatus.json", "w") as f:
    import json
    json.dump(response.json(), f)