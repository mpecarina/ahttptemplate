import ahttptemplate
from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop

class PingTestCase(AioHTTPTestCase):

    async def get_application(self):
        app = ahttptemplate.init_app()
        ahttptemplate.add_routes(app, {})
        return app

    @unittest_run_loop
    async def test_ping(self):
        resp = await self.client.get("/ping")
        resp_json = await resp.json()
        assert "PONG" in resp_json["info"]
