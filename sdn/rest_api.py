"""
SDN Project - REST API
Provides topology and shortest-path information.
"""

import json
import os

from ryu.base import app_manager
from ryu.app.wsgi import (
    ControllerBase,
    WSGIApplication,
    Response,
    route
)

from config import HOST_SWITCH, SWITCHES
from sdn.paths import get_primary_and_alternative_paths


REST_API_NAME = "sdn_rest_api"


class SDNRestAPI(app_manager.RyuApp):

    _CONTEXTS = {
        "wsgi": WSGIApplication
    }

    def __init__(self, *args, **kwargs):
        super(SDNRestAPI, self).__init__(*args, **kwargs)

        self.project_dir = os.path.dirname(
            os.path.dirname(os.path.abspath(__file__))
        )

        self.topology_file = os.path.join(
            self.project_dir,
            "data",
            "topology.json"
        )

        wsgi = kwargs["wsgi"]

        wsgi.register(
            SDNRestController,
            {REST_API_NAME: self}
        )

        self.logger.info("SDN REST API initialized")


class SDNRestController(ControllerBase):

    def __init__(self, req, link, data, **config):
        super(SDNRestController, self).__init__(
            req, link, data, **config
        )

        self.rest_app = data[REST_API_NAME]

    def json_response(self, data, status=200):

        return Response(
            content_type="application/json",
            body=json.dumps(data, indent=4),
            status=status
        )

    # GET /diag/topology
    @route(
        "diag_topology",
        "/diag/topology",
        methods=["GET"]
    )
    def get_topology(self, req, **kwargs):

        try:
            with open(
                self.rest_app.topology_file,
                "r"
            ) as file:
                topology = json.load(file)

            return self.json_response(topology)

        except FileNotFoundError:

            return self.json_response({
                "error": "Topology file not found. Start Mininet first."
            }, 503)

        except Exception as error:

            return self.json_response({
                "error": str(error)
            }, 500)

    # GET /diag/paths?src=h1&dst=h2
    @route(
        "diag_paths",
        "/diag/paths",
        methods=["GET"]
    )
    def get_paths(self, req, **kwargs):

        src = req.GET.get("src")
        dst = req.GET.get("dst")

        if not src or not dst:

            return self.json_response({
                "error": "Please provide src and dst parameters."
            }, 400)

        # Convert host names to their attached switches.
        src_switch = HOST_SWITCH.get(
            src,
            src if src in SWITCHES else None
        )

        dst_switch = HOST_SWITCH.get(
            dst,
            dst if dst in SWITCHES else None
        )

        if not src_switch or not dst_switch:

            return self.json_response({
                "error": "Invalid source or destination.",
                "valid_hosts": list(HOST_SWITCH.keys()),
                "valid_switches": SWITCHES
            }, 400)

        try:

            result = get_primary_and_alternative_paths(
                src_switch,
                dst_switch
            )

            if result["primary"] is None:

                return self.json_response({
                    "error": "No path available between requested nodes."
                }, 404)

            response_data = {
                "source": src,
                "destination": dst,
                "source_switch": src_switch,
                "destination_switch": dst_switch,
                "primary": result["primary"],
                "alternative": result["alternative"]
            }

            return self.json_response(response_data)

        except FileNotFoundError:

            return self.json_response({
                "error": "Topology file not found."
            }, 503)

        except Exception as error:

            self.rest_app.logger.exception(
                "Path API failed"
            )

            return self.json_response({
                "error": str(error)
            }, 500)
