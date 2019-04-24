Content-Type: multipart/mixed; boundary="//"
MIME-Version: 1.0

--//
Content-Type: text/cloud-config; charset="us-ascii"
MIME-Version: 1.0
Content-Transfer-Encoding: 7bit
Content-Disposition: attachment; filename="cloud-config.txt"

#cloud-config
cloud_final_modules:
- [scripts-user, always]

--//
Content-Type: text/x-shellscript; charset="us-ascii"
MIME-Version: 1.0
Content-Transfer-Encoding: 7bit
Content-Disposition: attachment; filename="userdata.txt"

#!/bin/bash
amazon-linux-extras install epel
yum update --security -y
yum install --enablerepo=epel -y nodejs

amazon-linux-extras install docker -y
service docker start
systemctl enable docker

AwsRegion=$(curl -s 169.254.169.254/latest/meta-data/placement/availability-zone | sed 's/.$//')
yum install -y git awslogs
sed -i -e "s/us-east-1/$AwsRegion/g" /etc/awslogs/awscli.conf
sed -i -e 's/log_group_name = \/var\/log\/messages/log_group_name = [CloudWatchIdentifier]/g' /etc/awslogs/awslogs.conf
sed -i -e 's/log_stream_name = {instance_id}/log_stream_name = messages-stack/g' /etc/awslogs/awslogs.conf
sed -i -e 's/\/var\/log\/messages/\/var\/log\/messages-stack/g' /etc/awslogs/awslogs.conf
systemctl start awslogsd
systemctl enable awslogsd.service
echo 'Start service in [nameMaster]' > /var/log/messages-stack
#git config --system credential.helper '!aws codecommit credential-helper $@'
#git config --system credential.UseHttpPath true
rm -rf /scripts
mkdir /scripts
cd /scripts
git clone https://github.com/sbraer/AwsNodeJsCodeDeploy.git
cd AwsNodeJsCodeDeploy/
npm install
chmod +x create_swarm.sh
chmod +x update_service.sh
crontab -r
chmod +x docker_login.sh
./docker_login.sh
(crontab -l 2>/dev/null; echo "0 */6 * * * /scripts/AwsNodeJsCodeDeploy/docker_login.sh -with args") | crontab -
./create_swarm.sh [ipPrivateList]
--//