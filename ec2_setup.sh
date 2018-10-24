#!/usr/bin/env bash

virtualenv -p python36 aws
source aws/bin/activate
sudo yum install git
git clone https://github.com/pseeth/aws-bsseval
cd aws-bsseval/
pip install -r requirements.txt
pip install boto3