import numpy as np
from museval import eval_dir
import zipfile
import json
import os
import boto3
from subprocess import call
import argparse
import urllib
from si_sdr import sdr_permutation_search
from scipy.io import wavfile

s3 = boto3.resource('s3', region_name='us-east-1')
s3_client = boto3.client('s3', region_name='us-east-1')
ec2_client = boto3.client('ec2', region_name='us-east-1')

def _load_audio(file_path):
    print(file_path)
    #loading audio for SI-SDR
    rate, audio = wavfile.read(file_path)
    print(audio.shape)
    if len(audio.shape) > 1:
        #SI-SDR only works with mono signals
        audio = audio[0]
    print(audio.shape)
    audio = audio.astype(np.float32, order='C') / 32768.0
    return audio, rate

def clear_temp():
    call('rm -rf /tmp/*', shell=True)

def setup(event):
    clear_temp()
    source_bucket = event['Records'][0]['s3']['bucket']['name']
    file_key = event['Records'][0]['s3']['object']['key']
    file_key = urllib.parse.unquote_plus(file_key)
    return source_bucket, file_key

def download_and_unzip(source_bucket, file_key, zip_path):
    print("Unzipping folder: %s" % file_key)
    bucket = s3.Bucket(source_bucket)
    bucket.download_file(file_key, zip_path)

    zip_ref = zipfile.ZipFile(zip_path, 'r')
    zip_ref.extractall('/tmp/')
    zip_ref.close()
    return bucket

def eval_si_sdr(reference_dir, estimate_dir, compute_permutation):
    references = [_load_audio(os.path.join(reference_dir, f))[0] for f in sorted(os.listdir(reference_dir))]
    estimates = [_load_audio(os.path.join(estimate_dir, f))[0] for f in sorted(os.listdir(estimate_dir))]

    mix = np.sum(np.stack(references), axis=0)
    print([x.shape for x in references])
    print([x.shape for x in estimates])
    print(mix.shape)

    if compute_permutation:
        metrics = sdr_permutation_search(mix, references, estimates)
    else:
        raise ValueError("Only permutation search currently implemented")

    results = {}
    for i in range(len(references)):
        results['s' + str(i+1)] = {'SDR': metrics[i,0],
                                 'SIR': metrics[i,1],
                                 'SAR': metrics[i,2]}
    return json.dumps(results)

def evaluate(file_key, file_name):
    base_path = os.path.join('/tmp', file_name[:-4])
    reference_dir = os.path.join(base_path, 'references')
    estimate_dir = os.path.join(base_path, 'estimates')
    compute_permutation = 'permute' in file_key
    use_si_sdr = 'si_sdr' in file_key

    print("Evaluating reference_dir (%s) and estimates_dir (%s) with permutation: %s" % (reference_dir, estimate_dir, str(compute_permutation)))

    if use_si_sdr:
        print("Using local SI-SDR")
        scores = eval_si_sdr(reference_dir, estimate_dir, compute_permutation)
        print(scores)
    else:
        print("Using BSSEval v4 from museval")
        scores = eval_dir(reference_dir,
                          estimate_dir,
                          compute_permutation=compute_permutation,
                          mode='v4')
        print(scores)
        scores = scores.json

    return scores

def run(source_bucket, file_key):
    file_name = file_key.split('/')[-1]
    zip_path = os.path.join('/tmp', file_name)
    bucket = download_and_unzip(source_bucket, file_key, zip_path)
    scores = evaluate(file_key, file_name)

    results_key = os.path.join('results', file_name[:-4] + '.json')
    print("Saving results")
    bucket.put_object(Key=results_key,
                      Body=scores)
    print("Deleting original audio")
    s3.Object(source_bucket, file_key).delete()
    clear_temp()

def run_on_ec2(source_bucket, file_key, instance_type='t3.large'):
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
        sudo poweroff
    """

    ec2_init_script = ec2_init_script.replace('SOURCE_BUCKET', '"' + source_bucket + '"')
    ec2_init_script = ec2_init_script.replace('FILE_KEY', '"' + file_key + '"')
    print("Running \n %s \n on EC2" % ec2_init_script)
    instance = ec2_client.run_instances(
        ImageId='ami-01103c7b',
        InstanceType=instance_type,
        MinCount=1,
        MaxCount=1,
        InstanceInitiatedShutdownBehavior='terminate',
        KeyName='aws',
        UserData=ec2_init_script,
        IamInstanceProfile={
            'Name': 'ec2-s3'
        },
        SecurityGroupIds=['launch-wizard-1']
    )
    print("Created instance: %s" % instance['Instances'][0]['InstanceId'])

def main(event, context):
    source_bucket, file_key = setup(event)
    print(source_bucket, file_key)
    response = s3_client.head_object(Bucket=source_bucket, Key=file_key)
    size = float(response['ContentLength']) / 1e6
    if size > 50:
        print("Audio files are too big for Lambda, moving computation to EC2.")
        run_on_ec2(source_bucket, file_key)
    else:
        run(source_bucket, file_key)

def process_remaining_on_local(source_bucket):
    bucket = s3.Bucket(source_bucket)
    for object in bucket.objects.all():
        if 'uploads' in object.key and '.zip' in object.key:
            print('Processing %s on local' % object.key)
            run(source_bucket, object.key)
    return

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source_bucket", default='bsseval')
    parser.add_argument("--file_key", default='uploads/test.zip')
    parser.add_argument("--process_remaining_on_local", action='store_true')
    args = parser.parse_args()
    source_bucket = args.source_bucket
    file_key = args.file_key

    if args.process_remaining_on_local:
        process_remaining_on_local(source_bucket)
    else:
        run(source_bucket, file_key)
