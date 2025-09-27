manage-aws
==========

Personal AWS account management for open source purpose.
Written in AWS CDK (Python compiled to CloudFormation), thanks to that the AWS is managing the state. 

There is no GitHub Actions pipeline intentionally, as this is a private AWS account I do not give any access to it anywhere.
The GitHub Actions in kube-cicd is using only a very restricted role.

### Bootstrapping

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cdk synth
```

### Deploying

```bash
cdk deploy
```
