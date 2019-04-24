const appRouter = (app) => {
    const { exec } = require("child_process");

    const execFunction = (command, res, returnOutput) => {
        exec(command, (error, stdout, stderr) => {
            if (stdout) {
                returnOutput ? res.status(200).send(stdout) : res.sendStatus(204);
            }
            else if (stderr) {
                res.status(400).send({ error: stderr });
            }
            else if (error !== null) {
                res.status(400).send({ error: error });
            }
            else {
                res.sendStatus(500);
            }
        });
    };

    app.get("/api/dockerswarm/token/:type", (req, res) => {
        const { type } = req.params;

        if (!type || (type !== "worker" && type !== "manager")) {
            res.status(400).send({ message: 'invalid token type supplied (manager|worker)' });
        }
        else {
            const dockerCommand = `docker swarm join-token ${type} | sed -n 3p | grep -Po 'docker swarm join --token \\K[^\\s]*'`;
            execFunction(dockerCommand, res, true);
        }
    });

    app.put("/api/dockerswarm/service", (req, res) => {
        const { servicename, image, portdocker, portmachine, region } = req.body;

        if (!servicename || /^([a-zA-Z0-9]{1,50})$/.test(servicename) === false) {
            res.status(400).send({ message: 'invalid servicename supplied' });
        }
        else if (!image || image.length > 250) {
            res.status(400).send({ message: 'invalid image supplied' });
        }
        else if (!isFinite(portdocker)) {
            res.status(400).send({ message: 'invalid portdocker supplied 1024-65535' });
        }
        else if (!isFinite(portmachine)) {
            res.status(400).send({ message: 'invalid portmachine supplied 1024-65535' });
        }
        else if (!region || region.length > 50) {
            res.status(400).send({ message: 'invalid region supplied' });
        }
        else {
            const dockerCommand = `sh ./update_service.sh "${servicename}" "${image}" "${portdocker}" "${portmachine}" "${region}"`;
            execFunction(dockerCommand, res, false);
        }
    });
}

module.exports = appRouter;

//curl -X PUT -H "Content-Type: application/json" -d '{"servicename":"mkyong","image":"immagineDocker","portdocker":"5000","portmachine":"5000"}' http://localhost:64000/api/dockerswarm/service
//curl localhost:64000/api/test

//curl -X PUT -H "Content-Type: application/json" -d '{"servicename":"app0","image":"sbraer/aspnetcorelinux:api1","portdocker":"5000","portmachine":"5000","region":"eu-central-1"}' http://localhost:64000/api/dockerswarm/service


/*
docker node ls -f "label=web"

docker service create --mode global --constraint engine.labels.web==true --name app0 -p 5000:5000 --network mynet sbraer/aspnetcorelinux:api1
curl localhost:5000/api/systeminfo

curl -X PUT -H "Content-Type: application/json" -d '{"servicename":"app0","image":"sbraer/aspnetcorelinux:api1","portdocker":"5000","portmachine":"5000","region":"eu-central-1"}' http://192.168.0.250:64000/api/dockerswarm/service


*/