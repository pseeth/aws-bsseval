import numpy as np
from museval import eval_dir
import zipfile
import json
import os

def unzip(zip_path):
	zip_ref = zipfile.ZipFile(zip_path, 'r')
	zip_ref.extractall('/tmp/')
	zip_ref.close()

def main(event, context):
	print(event)
	print("Evaluating estimates")
	unzip('eval.zip')
	scores = eval_dir('/tmp/eval/references', '/tmp/eval/estimates')
	print(scores)
	print("Writing to scores.json")
	return scores.json

if __name__ == "__main__":
	main('','')
