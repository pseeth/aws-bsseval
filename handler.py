import numpy as np
from museval import eval_dir
import zipfile
import json

def main(event, context):
	print("Evaluating estimates")
	scores = eval_dir('eval/references', 'eval/estimates')
	print("Writing to scores.json")
	with ("scores.json", "w") as f:
		json.dump(scores.scores, f, indent=2, allow_nan=True)

if __name__ == "__main__":
	main('','')
