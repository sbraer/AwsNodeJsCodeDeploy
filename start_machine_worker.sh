#!/bin/bash
yum update --security -y
amazon-linux-extras install docker -y
sed -i '/ExecStart=\/usr\/bin\/dockerd $OPTIONS $DOCKER_STORAGE_OPTIONS/cExecStart=\/usr\/bin\/dockerd $OPTIONS $DOCKER_STORAGE_OPTIONS --label=[label]=true' /lib/systemd/system/docker.service
service docker start
systemctl enable docker

yum install -y git

#git config --system credential.helper '!aws codecommit credential-helper $@'
#git config --system credential.UseHttpPath true
mkdir /scripts
cd /scripts
git clone https://github.com/sbraer/AwsNodeJsCodeDeploy.git
cd AwsNodeJsCodeDeploy/
chmod +x join_to_swarm.sh
./join_to_swarm.sh [ipPrivateList]