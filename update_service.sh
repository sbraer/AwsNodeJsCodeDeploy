#!/bin/bash
SERVICENAME=$1
IMAGEDOCKER=$2
PORTDOCKER=$3
PORTMACHINE=$4
REGION=$5

# Check parameters
if [ -z "$SERVICENAME" ]; then
        exit 1
fi
if [ -z "$IMAGEDOCKER" ]; then
        exit 1
fi
if [ -z "$PORTDOCKER" ]; then
        exit 1
fi
if [ -z "$PORTMACHINE" ]; then
        exit 1
fi
if [ -z "$REGION" ]; then
        exit 1
fi

# login into AWS docker repository
eval $(aws ecr get-login --region $REGION --no-include-email)
if [ ! $? -eq 0 ]; then
        exit 2
fi

# Check if service is already installed/running
docker service ps $SERVICENAME
if [ $? -eq 0 ]; then
        # echo OK
        docker service update --with-registry-auth --force --update-parallelism 1 --update-delay 30s $SERVICENAME # update service
else
        # echo FAIL
        docker service create --network mynet --with-registry-auth --name $SERVICENAME -p $PORTMACHINE:$PORTDOCKER $IMAGEDOCKER # install service
fi