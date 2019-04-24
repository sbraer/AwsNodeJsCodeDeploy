#!/bin/bash
echo "join to swarm..."
w1=$1
w2=$2
w3=$3
w=($w1 $w2 $w3)
exitFile="false"
while true
do
    for i in "${w[@]}"
    do
        code=$(curl --fail --connect-timeout 5 http://$i:64000/api/dockerswarm/token/worker)
        if [ ! -z "$code" ]; then
            echo "API Rest repied. Try to join to manager..."
            eval "docker swarm join --token $code $i"
            if [ $? -eq 0 ]; then
                    echo "joined!"
                    exitFile="true"
                    break
            fi
        fi
    done

    if [ "$exitFile" = "true" ]; then
            break
    fi

    echo "Wait 30 seconds..."
    sleep 30
done