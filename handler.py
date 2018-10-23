import numpy as np
from museval import eval_dir
import zipfile
import json
import os
import boto3

s3 = boto3.resource('s3')

def unzip(zip_path):
    zip_ref = zipfile.ZipFile(zip_path, 'r')
    zip_ref.extractall('/tmp/')
    zip_ref.close()

def main(event, context):
    source_bucket = event['Records'][0]['s3']['bucket']['name']
    file_key = event['Records'][0]['s3']['object']['key']
    file_name = file_key.split('/')[-1]
    zip_path = os.path.join('/tmp', file_name)
    bucket = s3.Bucket(source_bucket)
    bucket.download_file(file_key, zip_path)
    print("Unzipping folder")
    unzip(zip_path)

    base_path = os.path.join('/tmp', file_name[:-4])
    reference_dir = os.path.join(base_path, 'references')
    estimate_dir = os.path.join(base_path, 'estimates')
    results_key = os.path.join('results', file_name[:-4] + '.json')

    print("Evaluating estimates")
    scores = eval_dir(reference_dir, estimate_dir)
    print(scores)

    print("Saving results")
    bucket.put_object(Key=results_key,
                      Body=scores.json)
    print("Deleting original audio")
    bucket.delete_key(file_key)

    return scores.json

if __name__ == "__main__":
    main('','')
