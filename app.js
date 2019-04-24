const express = require("express"),
    bodyParser = require("body-parser"),
    dockerSwarmApi = require("./routes/dockerswarm.js"),
    testApi = require("./routes/test.js");
const app = express();

app.use(bodyParser.json());
app.use(bodyParser.urlencoded({ extended: true }));

dockerSwarmApi(app);
testApi(app);

app.use((_, res) => {
    res.sendStatus(404);
});

// PORT=3000 node app.js
const port = process.env.PORT || 64000;
const server = app.listen(port, () => {
    console.log("app running on port: ", server.address().port);
});

/*
PACKAGE_VERSION=$(cat package.json \
  | grep version \
  | head -1 \
  | awk -F: '{ print $2 }' \
  | sed 's/[",]//g' \
  | tr -d '[[:space:]]')

echo $PACKAGE_VERSION
*/