const appRouter = (app) => {
    app.get("/api/test", (_, res) => {
        res.status(200).send({ test: 1 });
    });
}

module.exports = appRouter;
