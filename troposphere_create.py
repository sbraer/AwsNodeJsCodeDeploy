#!/usr/bin/python
# Value of property VPCZoneIdentifier must be of type List of String
from awacs.aws import Allow, Statement, Principal, Action
from awacs.sts import AssumeRole
from troposphere import Parameter, Ref, Sub, Template, Tags, Select, GetAZs, Base64, Output, GetAtt, FindInMap
from troposphere.iam import Role, InstanceProfile, Policy
from troposphere.ec2 import Route, \
    VPCGatewayAttachment, SubnetRouteTableAssociation, Subnet, RouteTable, \
    VPC, InternetGateway, \
    SecurityGroupRule, SecurityGroup
import troposphere.ec2 as ec2
import awacs.aws
from troposphere.autoscaling import AutoScalingGroup, Tag, LaunchConfiguration
from troposphere.policies import (
    AutoScalingReplacingUpdate, AutoScalingRollingUpdate, UpdatePolicy
)
from troposphere.cloudwatch import Alarm, MetricDimension
from troposphere.autoscaling import LaunchConfiguration, ScalingPolicy, StepAdjustments

###############################################################################################

USER_DATA_MASTER = """Content-Type: multipart/mixed; boundary="//"
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

# Use this command if you only want to support EBS
docker plugin install --alias cloudstor:aws --grant-all-permissions docker4x/cloudstor:18.03.0-ce-aws1 CLOUD_PLATFORM=AWS AWS_REGION=$AwsRegion EFS_SUPPORTED=0 DEBUG=1

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
--//"""
USER_DATA_WORKER = """#!/bin/bash
yum update --security -y
amazon-linux-extras install docker -y
sed -i '/ExecStart=\/usr\/bin\/dockerd $OPTIONS $DOCKER_STORAGE_OPTIONS/cExecStart=\/usr\/bin\/dockerd $OPTIONS $DOCKER_STORAGE_OPTIONS --label=[label]=true' /lib/systemd/system/docker.service
service docker start
systemctl enable docker

AwsRegion=$(curl -s 169.254.169.254/latest/meta-data/placement/availability-zone | sed 's/.$//')
yum install -y git
# Use this command if you only want to support EBS
docker plugin install --alias cloudstor:aws --grant-all-permissions docker4x/cloudstor:18.03.0-ce-aws1 CLOUD_PLATFORM=AWS AWS_REGION=$AwsRegion EFS_SUPPORTED=0 DEBUG=1

#git config --system credential.helper '!aws codecommit credential-helper $@'
#git config --system credential.UseHttpPath true
mkdir /scripts
cd /scripts
git clone https://github.com/sbraer/AwsNodeJsCodeDeploy.git
cd AwsNodeJsCodeDeploy/
chmod +x join_to_swarm.sh
./join_to_swarm.sh [ipPrivateList]
"""


###############################################################################################
class SecurityGroupClass(object):
    def __init__(self, name=None, cidrBlock = "", type = "", fromPort = -1, toPort = -1):
        self.name = name
        self.cidrBlock = cidrBlock
        self.type = type
        self.fromPort = fromPort
        self.toPort = toPort
        self.instance = None


class Ec2Machine(object):
    def __init__(self, name=None, ip=None, instanceType="t2.micro"):
        self.name = name
        self.ip = ip
        self.instanceType = instanceType
        self.instance = None


class SubnetClass(object):
    def __init__(self, name=None, cidrBlock=None, availabilityZone=None, mapPublicIpOnLaunch=None):
        self.name = name
        self.CidrBlock = cidrBlock
        self.AvailabilityZone = availabilityZone
        self.MapPublicIpOnLaunch = mapPublicIpOnLaunch
        self.instance = None
        self.ec2 = None


class VpcClass(object):
    def __init__(self, name=None, cidrBlock=None):
        self.name = name
        self.CidrBlock = cidrBlock
        self.subnets = []
        self.instance = None
#######################################################################################


environmentString = "MyEnvironment-"  # <-- Add dash here
cloudWatchIdentifier = "Stack2"
instanceTypeMaster = "t2.micro"
instanceTypeWorker = "t2.micro"

DesiredCapacity = 1
MinSize = 1
MaxSize = 3

labels = ["web"]
#labels = ["web", "db"]

CodeCommitResource = ["arn:aws:codecommit:eu-central-1:838080890745:AwsCodeTest"]  # or [] to disable this role
vpc = VpcClass("myVPC", "192.168.0.0/16")
vpc.subnets.append(SubnetClass("Subnet1", "192.168.0.0/20", 0, True))
vpc.subnets.append(SubnetClass("Subnet2", "192.168.16.0/20", 1, True))
vpc.subnets.append(SubnetClass("Subnet3", "192.168.32.0/20", 2, True))

vpc.subnets[0].ec2 = Ec2Machine("MasterA", "192.168.0.250", instanceTypeMaster)
#vpc.subnets[1].ec2 = Ec2Machine("MasterB", "192.168.16.250", instanceTypeMaster)
#vpc.subnets[2].ec2 = Ec2Machine("MasterC", "192.168.32.250", instanceTypeMaster)

securityMasterIngress = [
    # Used from docker for Swarm Managers
    SecurityGroupClass("DockerClusterManagementCommunications", vpc.CidrBlock, "tcp", 2376, 2377),
    SecurityGroupClass("DockerForCommunicationAmongNodesTcp", vpc.CidrBlock, "tcp", 7946, 7946),
    SecurityGroupClass("DockerForCommunicationAmongNodesUdp", vpc.CidrBlock, "udp", 7946, 7946),
    SecurityGroupClass("DockerForOverlayNetworkTraffic", vpc.CidrBlock, "udp", 4789, 4789),
    # My inbound ports
    SecurityGroupClass("ssh", "0.0.0.0/0", "tcp", 22, 22),
    SecurityGroupClass("http64000", vpc.CidrBlock, "tcp", 64000, 64000)
]

securityMasterEgress = [
    SecurityGroupClass("Input", "0.0.0.0/0", "-1"),
]

securityWorkerIngress = [
    # Used from docker for Swarm Workers
    SecurityGroupClass("DockerForCommunicationAmongNodesTcp", vpc.CidrBlock, "tcp", 7946, 7946),
    SecurityGroupClass("DockerForCommunicationAmongNodesUdp", vpc.CidrBlock, "udp", 7946, 7946),
    SecurityGroupClass("DockerForOverlayNetworkTraffic", vpc.CidrBlock, "udp", 4789, 4789),
    # My inbound ports
    SecurityGroupClass("ssh", "0.0.0.0/0", "tcp", 22, 22),
    SecurityGroupClass("testdocker", "0.0.0.0/0", "tcp", 5000, 5001),
]

securityWorkerEgress = [
    SecurityGroupClass("Input", "0.0.0.0/0", "-1"),
]

ipPrivateList = ""
for f in vpc.subnets:
    if f.ec2 is not None:
        if len(ipPrivateList) > 0:
            ipPrivateList += " "
        ipPrivateList += f.ec2.ip

template = Template("This template deploys a VPC, with a pair of public and private subnets spread across two Availability Zones. It deploys an Internet Gateway, with a default route on the public subnets. It deploys a pair of NAT Gateways (one in each AZ), and default routes for them in the private subnets.")
template.set_version("2010-09-09")
########################## MAPPING #####################################################

template.add_mapping('RegionMap', {
    "ap-south-1":      {"AMI": "ami-0937dcc711d38ef3f"},
    "eu-west-3":      {"AMI": "ami-0854d53ce963f69d8"},
    "eu-north-1":      {"AMI": "ami-6d27a913"},
    "eu-west-2":      {"AMI": "ami-0664a710233d7c148"},
    "eu-west-1": {"AMI": "ami-0fad7378adf284ce0"},
    "ap-northeast-2": {"AMI": "ami-018a9a930060d38aa"},
    "ap-northeast-1": {"AMI": "ami-0d7ed3ddb85b521a6"},
    "sa-east-1": {"AMI": "ami-0b04450959586da29"},
    "ca-central-1": {"AMI": "ami-0de8b8e4bc1f125fe"},
    "ap-southeast-1": {"AMI": "ami-04677bdaa3c2b6e24"},
    "ap-southeast-2": {"AMI": "ami-0c9d48b5db609ad6e"},
    "eu-central-1": {"AMI": "ami-0eaec5838478eb0ba"},
    "us-east-1": {"AMI": "ami-035be7bafff33b6b6"},
    "us-east-2": {"AMI": "ami-04328208f4f0cf1fe"},
    "us-west-1": {"AMI": "ami-0799ad445b5727125"},
    "us-west-2": {"AMI": "ami-032509850cf9ee54e"}
})

########################################################################################
keyPar_param = template.add_parameter(Parameter(
    "KeyPairName",
    Description="Key used with SSH",
    Type="AWS::EC2::KeyPair::KeyName"
))

#########################################################################################

policies = []
if len(CodeCommitResource) > 0:
    policies.append(Policy(
            PolicyName=environmentString + "GitPolicy",
            PolicyDocument=awacs.aws.Policy(
                Statement=[
                    Statement(
                        Effect=Allow,
                        Action=[Action("codecommit", "ListRepositories")],
                        Resource=["*"]
                    ),
                    Statement(
                        Effect=Allow,
                        Action=[Action("codecommit", "GitPull")],
                        Resource=CodeCommitResource
                    ),
                ],
            )
        ))

policies.append(Policy(
            PolicyName=environmentString + "CWMyLogPolicy",
            PolicyDocument=awacs.aws.Policy(
                Statement=[
                    Statement(
                        Effect=Allow,
                        Action=[
                            Action("logs", "CreateLogGroup"),
                            Action("logs", "CreateLogStream"),
                            Action("logs", "PutLogEvents"),
                            Action("logs", "DescribeLogStreams"),
                        ],
                        Resource=["arn:aws:logs:*:*:*"]
                    )
                ]
            )
        )
    )

policies.append(Policy(
            PolicyName=environmentString + "CloudStor",
            PolicyDocument=awacs.aws.Policy(
                Statement=[
                    Statement(
                        Effect=Allow,
                        Action=[
                            Action("ec2", "CreateTags"),
                            Action("ec2", "AttachVolume"),
                            Action("ec2", "DetachVolume"),
                            Action("ec2", "CreateVolume"),
                            Action("ec2", "DeleteVolume"),
                            Action("ec2", "DescribeVolumes"),
                            Action("ec2", "DescribeVolumeStatus"),
                            Action("ec2", "CreateSnapshot"),
                            Action("ec2", "DeleteSnapshot"),
                            Action("ec2", "DescribeSnapshots")
                        ],
                        Resource=["*"]
                    )
                ]
            )
        )
    )

rootRole = template.add_resource(Role(
    "RootRole",
    AssumeRolePolicyDocument=awacs.aws.Policy(
        Statement=[
            Statement(
                Effect=Allow,
                Action=[AssumeRole],
                Principal=Principal("Service", ["ec2.amazonaws.com"])
            )
        ]
    ),
    ManagedPolicyArns=[
        "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryPowerUser",
        "arn:aws:iam::aws:policy/service-role/AmazonEC2RoleforSSM"
    ],
    Path="/",
    Policies= policies
))

rootInstanceProfile = template.add_resource(InstanceProfile(
    "RootInstanceProfile",
    Path="/",
    Roles=[Ref(rootRole)]
))

############################# VPC AND SUBNET ###########################################
VPC = template.add_resource(
    VPC(
        'VPC',
        CidrBlock=vpc.CidrBlock,
        EnableDnsSupport=True,
        EnableDnsHostnames=True,
        Tags=Tags(
            Name=environmentString + "VPC",
            Stack=Ref("AWS::StackName")
        ))
)
vpc.instance = VPC

for f in vpc.subnets:
    subnet = template.add_resource(
        Subnet(
            f.name,
            CidrBlock=f.CidrBlock,
            VpcId=Ref(VPC),
            MapPublicIpOnLaunch=f.MapPublicIpOnLaunch,
            AvailabilityZone=Select(f.AvailabilityZone, GetAZs()),
            Tags=Tags(
                Name=environmentString + f.name,
                Stack=Ref("AWS::StackName")
            )
        )
    )
    f.instance = subnet

############################# ADD GATEWAY AND ROLE ###########################
internetGateway = template.add_resource(
    InternetGateway(
        'InternetGateway',
        Tags=Tags(
            Name=environmentString + "Internet-Gateway",
            Stack=Ref("AWS::StackName")
        )
    )
)

gatewayAttachment = template.add_resource(
    VPCGatewayAttachment(
        'AttachGateway',
        VpcId=Ref(VPC),
        InternetGatewayId=Ref(internetGateway)))

routeTable = template.add_resource(
    RouteTable(
        'PublicRouteTable',
        VpcId=Ref(VPC),
        Tags=Tags(
            Name=environmentString + "Public-Routes",
            Stack=Ref("AWS::StackName")
        )
    )
)

route = template.add_resource(
    Route(
        'Route',
        DependsOn='AttachGateway',
        GatewayId=Ref('InternetGateway'),
        DestinationCidrBlock='0.0.0.0/0',
        RouteTableId=Ref(routeTable),
    )
)

######################### ADD ROUTE TO SUBNET ###########################
for f in vpc.subnets:
    template.add_resource(
        SubnetRouteTableAssociation(
            'SubnetRouteTableAssociation'+f.name,
            SubnetId=Ref(f.instance),
            RouteTableId=Ref(routeTable),
        )
    )

###################### Add PORT #####################################

securityGroupIngress = []
securityGroupEgress = []

for f in securityMasterIngress:
    securityGroupIngress.append(SecurityGroupRule(
        IpProtocol=f.type,
        FromPort=f.fromPort,
        ToPort=f.toPort,
        CidrIp=f.cidrBlock
    ))

for f in securityMasterEgress:
    securityGroupEgress.append(SecurityGroupRule(
        IpProtocol=f.type,
        FromPort=f.fromPort,
        ToPort=f.toPort,
        CidrIp=f.cidrBlock
    ))

instanceSecurityGroup = template.add_resource(
    SecurityGroup(
        environmentString.replace("-", "")+'CustomSecurityGroupIngressMaster',
        GroupDescription='CustomSecurity Group Ingress Master',
        SecurityGroupIngress=securityGroupIngress,
        SecurityGroupEgress=securityGroupEgress,
        VpcId=Ref(VPC),
        Tags=Tags(
            Name=environmentString + "CustomSecurityGroupIngressMaster",
            Stack=Ref("AWS::StackName")
        )
    )
)

########################### create ec2 master ##################################
for f in vpc.subnets:
    if f.ec2 is not None:
        instance = template.add_resource(ec2.Instance(
            f.ec2.name,
            DisableApiTermination="false",
            InstanceInitiatedShutdownBehavior="stop",
            IamInstanceProfile=Ref(rootInstanceProfile),
            ImageId=FindInMap("RegionMap", Ref("AWS::Region"), "AMI"),
            InstanceType=f.ec2.instanceType,
            KeyName=Ref(keyPar_param),
            UserData=Base64(USER_DATA_MASTER
                .replace("[ipPrivateList]", ipPrivateList)
                .replace("[CloudWatchIdentifier]", cloudWatchIdentifier)
                .replace("[nameMaster]", f.ec2.name)
                ),
            Tags=Tags(
                Name=environmentString + f.ec2.name,
                Stack=Ref("AWS::StackName")
            ),
            NetworkInterfaces=[
                ec2.NetworkInterfaceProperty(
                    DeleteOnTermination="true",
                    Description="Primary network interface",
                    DeviceIndex="0",
                    SubnetId=Ref(f.instance),
                    AssociatePublicIpAddress="true",
                    PrivateIpAddresses=[
                        ec2.PrivateIpAddressSpecification(
                            "PrivateIpAddress",
                            Primary="true",
                            PrivateIpAddress=f.ec2.ip
                        )
                    ],
                    GroupSet=[Ref(instanceSecurityGroup)]
                )
            ],
        ))
        f.ec2.instance = instance
        alarmMaster = template.add_resource(Alarm(
            "AlarmRecovery" + f.ec2.name,
            AlarmDescription="Recovery "+f.ec2.name,
            Namespace="AWS/EC2",
            MetricName="StatusCheckFailed_System",
            Dimensions=[
                MetricDimension(
                    Name="InstanceId",
                    Value=Ref(instance)
                ),
            ],
            Statistic="Maximum",
            Period="60",
            EvaluationPeriods="5",
            Threshold="0",
            ComparisonOperator="GreaterThanThreshold",
            AlarmActions=[Sub('arn:aws:automate:${AWS::Region}:ec2:recover')]
        ))

################################ Security autoscaling ###################################
subnetsList = []
for f in vpc.subnets:
    subnetsList.append(Ref(f.instance))

securityGroupIngressWorker = []
securityGroupEgressWorker = []

for f in securityWorkerIngress:
    securityGroupIngressWorker.append(SecurityGroupRule(
        IpProtocol=f.type,
        FromPort=f.fromPort,
        ToPort=f.toPort,
        CidrIp=f.cidrBlock
    ))

for f in securityWorkerEgress:
    securityGroupEgressWorker.append(SecurityGroupRule(
        IpProtocol=f.type,
        FromPort=f.fromPort,
        ToPort=f.toPort,
        CidrIp=f.cidrBlock
    ))

instanceSecurityWorkerGroup = template.add_resource(
    SecurityGroup(
        environmentString.replace("-", "")+'CustomSecurityGroupIngressWorker',
        GroupDescription='CustomSecurity Group Ingress Master',
        SecurityGroupIngress=securityGroupIngressWorker,
        SecurityGroupEgress=securityGroupEgressWorker,
        VpcId=Ref(VPC),
        Tags=Tags(
            Name=environmentString + "CustomSecurityGroupIngressWorker",
            Stack=Ref("AWS::StackName")
        )
    )
)


for f in labels:
    LaunchConfig = template.add_resource(LaunchConfiguration(
        "LaunchConfiguration"+f,
        ImageId=FindInMap("RegionMap", Ref("AWS::Region"), "AMI"),
        InstanceType=instanceTypeWorker,
        KeyName=Ref(keyPar_param),
        IamInstanceProfile=Ref(rootInstanceProfile),
        SecurityGroups=[Ref(instanceSecurityWorkerGroup)],
        UserData=Base64(USER_DATA_WORKER.replace("[ipPrivateList]", ipPrivateList).replace("[label]", f)),
        BlockDeviceMappings=[
            ec2.BlockDeviceMapping(
                DeviceName="/dev/xvda",
                Ebs=ec2.EBSBlockDevice(
                    VolumeSize="8"
                )
            )
        ]
        )
    )

    AutoscalingGroupX = template.add_resource(AutoScalingGroup(
        "AutoscalingGroup"+f,
        Cooldown=300,
        HealthCheckGracePeriod=300,
        DesiredCapacity=DesiredCapacity,
        MinSize=MinSize,
        MaxSize=MaxSize,
        Tags=[
            Tag("Name", environmentString+"AutoscalingGroup"+f, True)
        ],
        LaunchConfigurationName=Ref(LaunchConfig),
        VPCZoneIdentifier=subnetsList,
        # LoadBalancerNames=[Ref(LoadBalancer)],
        #AvailabilityZones=subnetsList,
        HealthCheckType="EC2",
        UpdatePolicy=UpdatePolicy(
            AutoScalingReplacingUpdate=AutoScalingReplacingUpdate(
                WillReplace=True,
            ),
            AutoScalingRollingUpdate=AutoScalingRollingUpdate(
                PauseTime='PT5M',
                MinInstancesInService="1",
                MaxBatchSize='1',
                WaitOnResourceSignals=True
            )
        )
    ))

    ScalePolicyUp = template.add_resource(ScalingPolicy(
        "HTTPRequestScalingPolicyUp"+f,
        AutoScalingGroupName=Ref(AutoscalingGroupX),
        AdjustmentType="ChangeInCapacity",
        Cooldown="300",
        ScalingAdjustment="1"
    ))

    ScalePolicyDown = template.add_resource(ScalingPolicy(
        "HTTPRequestScalingPolicyDown"+f,
        AutoScalingGroupName=Ref(AutoscalingGroupX),
        AdjustmentType="ChangeInCapacity",
        Cooldown="300",
        ScalingAdjustment="-1"
    ))

    HTTPRequestAlarmUp = template.add_resource(Alarm(
        "HTTPRequestAlarmUp"+f,
        AlarmDescription="Alarm if Network out is > 4.000.000",
        Namespace="AWS/EC2",
        MetricName="NetworkOut",
        Dimensions=[
            MetricDimension(
                Name="AutoScalingGroupName",
                Value=Ref(AutoscalingGroupX)
            ),
        ],
        Statistic="Average",
        Period="60", # 1 minute
        EvaluationPeriods="1",
        Threshold="4000000",
        ComparisonOperator="GreaterThanOrEqualToThreshold",
        AlarmActions=[Ref(ScalePolicyUp)]
    ))

    HTTPRequestAlarmDown = template.add_resource(Alarm(
        "HTTPRequestAlarmDown"+f,
        AlarmDescription="Alarm if Network is < 1.000.000",
        Namespace="AWS/EC2",
        MetricName="NetworkOut",
        Dimensions=[
            MetricDimension(
                Name="AutoScalingGroupName",
                Value=Ref(AutoscalingGroupX)
            ),
        ],
        Statistic="Average",
        Period="60", # 1 minute
        EvaluationPeriods="1",
        Threshold="1000000",
        ComparisonOperator="LessThanOrEqualToThreshold",
        AlarmActions=[Ref(ScalePolicyDown)]
    ))

###################################################################

outputs = []

outputs.append(Output(
        "VPC",
        Description="A reference to the created VPC",
        Value=Ref(VPC),
    ))

for f in vpc.subnets:
    if f.ec2 is not None:
        outputs.append(Output(
                "PublicIP"+f.ec2.name,
                Description="Public IP address of the newly created EC2 instance: " + f.ec2.name,
                Value=GetAtt(f.ec2.instance, "PublicIp")
            )
        )

for f in vpc.subnets:
    outputs.append(Output(
        f.name,
        Description="A reference to the public subnet in the availability Zone",
        Value=Ref(f.instance)
        )
    )

template.add_output(outputs)

print(template.to_yaml())
#print(template.to_json())
