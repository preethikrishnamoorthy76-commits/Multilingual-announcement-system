import requests
import json

url = "https://irctc1.p.rapidapi.com/api/v1/liveTrainStatus"

querystring = {"trainNo":"12269","startDay":"1"}

headers = {
	"x-rapidapi-key": "ad72945a94mshec277828411ed38p1d23e9jsn2796a5a3e79c",
	"x-rapidapi-host": "irctc1.p.rapidapi.com"
}

response = requests.get(url, headers=headers, params=querystring)

with open("train_"+str(querystring["trainNo"])+".json", 'w') as f:
    json.dump(response.json(), f)