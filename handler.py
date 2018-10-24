import numpy as np
from museval import eval_dir
import zipfile
import json
import os
import boto3
from subprocess import call
import argparse

s3 = boto3.resource('s3', region='us-east-1')
s3_client = boto3.client('s3', region='us-east-1')
ec2_client = boto3.client('ec2', region='us-east-1')

ec2_init_script = """
    #!/bin/bash
    cd ~
    virtualenv -p python36 aws
    source aws/bin/activate
    sudo yum install -y git
    git clone https://github.com/pseeth/aws-bsseval
    source aws/bin/activate
    cd aws-bsseval
    git pull origin master
    pip install -r requirements.txt
    pip install boto3
    python handler.py --source_bucket SOURCE_BUCKET --file_key FILE_KEY
"""


def clear_temp():
    call('rm -rf /tmp/*', shell=True)

def setup(event):
    clear_temp()
    source_bucket = event['Records'][0]['s3']['bucket']['name']
    file_key = event['Records'][0]['s3']['object']['key']
    file_key = file_key.replace('+', ' ')
    file_key = file_key.replace('%27', "'")
    return source_bucket, file_key

def download_and_unzip(source_bucket, file_key, zip_path):
    print("Unzipping folder: %s" % file_key)
    bucket = s3.Bucket(source_bucket)
    bucket.download_file(file_key, zip_path)

    zip_ref = zipfile.ZipFile(zip_path, 'r')
    zip_ref.extractall('/tmp/')
    zip_ref.close()
    return bucket

def evaluate(file_key, file_name):
    base_path = os.path.join('/tmp', file_name[:-4])
    reference_dir = os.path.join(base_path, 'references')
    estimate_dir = os.path.join(base_path, 'estimates')
    compute_permutation = 'permute' in file_key

    print("Evaluating estimates with permutation: %s" % str(compute_permutation))
    scores = eval_dir(reference_dir,
                      estimate_dir,
                      compute_permutation=compute_permutation,
                      mode='v4')
    print(scores)
    return scores

def run(source_bucket, file_key):
    file_name = file_key.split('/')[-1]
    zip_path = os.path.join('/tmp', file_name)
    bucket = download_and_unzip(source_bucket, file_key, zip_path)
    scores = evaluate(file_key, file_name)

    results_key = os.path.join('results', file_name[:-4] + '.json')
    print("Saving results")
    bucket.put_object(Key=results_key,
                      Body=scores.json)
    print("Deleting original audio")
    s3.Object(source_bucket, file_key).delete()
    clear_temp()

def run_on_ec2(source_bucket, file_key):
    global ec2_init_script
    ec2_init_script = ec2_init_script.replace('SOURCE_BUCKET', '"' + source_bucket + '"')
    ec2_init_script = ec2_init_script.replace('FILE_KEY', '"' + file_key + '"')
    print("Running \n %s \n on EC2" % ec2_init_script)
    instance = ec2_client.run_instances(
        ImageId='ami-01103c7b',
        InstanceType='t2.medium',
        MinCount=1,
        MaxCount=1,
        InstanceInitiatedShutdownBehavior='terminate',
        KeyName='aws',
        UserData=ec2_init_script,
        IamInstanceProfile={
            #'Arn': "arn:aws:sts::237978708207:assumed-role/ec2-s3/i-07df688387ef3f061",
            'Name': 'ec2-s3'
        },
        SecurityGroupIds=['launch-wizard-1']
    )
    print("Created instance: %s" % instance['Instances'][0]['InstanceId'])

def main(event, context):
    source_bucket, file_key = setup(event)
    response = s3_client.head_object(Bucket=source_bucket, Key=file_key)
    size = float(response['ContentLength']) / 1e6
    if size > 80:
        print("Audio files are too big for Lambda, moving computation to EC2.")
        run_on_ec2(source_bucket, file_key)
    else:
        run(source_bucket, file_key)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source_bucket")
    parser.add_argument("--file_key")
    args = parser.parse_args()

    source_bucket = args.source_bucket
    file_key = args.file_key

    run_on_ec2(source_bucket, file_key)
