import json

with open("/home/jsh/workspace/TrojanCloak/data/investigate.json", "r") as f:
    file = json.load(f)
dumped = []
for example in file:
    dumped.append(example["Title"])

with open("quick.json", "w") as f:
    json.dump(dumped, f)
