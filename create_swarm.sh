#!/bin/bash
IPMASTERA=$1
IPMASTERB=$2
IPMASTERC=$3

if [ -z "$IPMASTERB" ]; then
    IPMASTERB=""
fi

if [ -z "$IPMASTERC" ]; then
    IPMASTERC=""
fi

ip=$(curl http://169.254.169.254/latest/meta-data/local-ipv4)
if [ $ip = $IPMASTERA ]; then
        master1=$IPMASTERB # b
        master2=$IPMASTERC  # c
elif [ $ip = $IPMASTERB ]; then
        master1=$IPMASTERA # a
        master2=$IPMASTERC  # c
elif [ $ip = $IPMASTERC ]; then
        master1=$IPMASTERA # a
        master2=$IPMASTERB # b
else
        exit 255
fi

docker node ls
if [ $? -eq 0 ]; then
    eval "docker network create --driver overlay mynet"
    echo "Swarm already started and joined"
    echo "$ip already started and joined" >> /var/log/messages-stack
    node app.js &
    exit 0
fi
echo "Check..."
echo "$ip Check if there is docker swarm available..." >> /var/log/messages-stack
writeFiles="false"
files=($master1 $master2)

while true
do
    for i in "${files[@]}"
    do
        echo "Try to connect to $i..."
        echo "$ip Try to connect to $i..." >> /var/log/messages-stack
        code=$(curl --fail --connect-timeout 5 http://$i:64000/api/dockerswarm/token/manager)
        if [ ! -z "$code" ]; then
            echo "API Rest replied. Try to join to manager..."
            echo "$ip API Rest replied. Try to join to manager..." >> /var/log/messages-stack
            eval "docker swarm join --token $code $i"
            if [ $? -eq 0 ]; then
                echo "$ip joined!" >> /var/log/messages-stack
                eval "docker network create --driver overlay mynet"
                writeFiles="true"
                break
            fi
        fi
    done

    if [[ ! "$writeFiles" = "true" && "$ip" = $IPMASTERA ]]; then
        docker swarm init --advertise-addr $ip
        if [ ! $? -eq 0 ]; then
                echo "$ip Error creating Swarm" >> /var/log/messages-stack
                echo "Error when create Swarm"
                exit 255
        fi
        echo "$ip Swarm created" >> /var/log/messages-stack
        eval "docker network create --driver overlay mynet"
        break
    fi

    if [ "$writeFiles" = "true" ]; then
    break
    fi

    echo "Wait 30 seconds..."
    echo "$ip Wait 30 seconds..." >> /var/log/messages-stack
    sleep 30
done

echo "$ip Start API Rest" >> /var/log/messages-stack
node app.js &
exit 0
