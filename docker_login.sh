#!/bin/bash
echo "Login to AWS ECR" >> /var/log/messages-stack
$(aws ecr get-login --region eu-central-1 --no-include-email)
