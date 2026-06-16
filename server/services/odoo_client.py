import requests
from flask import current_app


class OdooJsonRpcError(RuntimeError):
    """Erreur remontée par l'API JSON-RPC Odoo."""


class OdooJsonRpcClient:
    """
    Client minimal pour l'API externe JSON-RPC d'Odoo.

    Responsabilités :
    - authentification via common.login ;
    - appels métier via object.execute_kw ;
    - helper read_group pour les futurs agrégats comptables.
    """

    def __init__(self):
        self.jsonrpc_url = current_app.config["ODOO_JSONRPC_URL"]
        self.db = current_app.config["ODOO_DB"]
        self.login_name = current_app.config["ODOO_LOGIN"]
        self.password = current_app.config["ODOO_PASSWORD"]

        self.uid = None
        self._request_id = 0

        self._validate_config()

    def _validate_config(self):
        missing = []

        if not self.jsonrpc_url:
            missing.append("ODOO_JSONRPC_URL ou ODOO_BASE_URL")
        if not self.db:
            missing.append("ODOO_DB")
        if not self.login_name:
            missing.append("ODOO_LOGIN")
        if not self.password:
            missing.append("ODOO_PASSWORD")

        if missing:
            raise ValueError(
                "Configuration Odoo incomplète dans .env : "
                + ", ".join(missing)
            )

    def _next_request_id(self):
        self._request_id += 1
        return self._request_id

    def _call(self, service, method, args, timeout=30):
        payload = {
            "jsonrpc": "2.0",
            "method": "call",
            "id": self._next_request_id(),
            "params": {
                "service": service,
                "method": method,
                "args": args,
            },
        }

        response = requests.post(
            self.jsonrpc_url,
            json=payload,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            timeout=timeout,
        )
        response.raise_for_status()

        data = response.json()

        if "error" in data:
            error = data["error"]
            error_data = error.get("data", {}) if isinstance(error, dict) else {}
            message = (
                error_data.get("message")
                or error.get("message") if isinstance(error, dict) else None
            )
            raise OdooJsonRpcError(
                f"Erreur JSON-RPC Odoo sur {service}.{method} : "
                f"{message or error}"
            )

        if "result" not in data:
            raise OdooJsonRpcError(
                f"Réponse JSON-RPC Odoo inattendue sur {service}.{method} : "
                "champ 'result' absent."
            )

        return data["result"]

    def login(self):
        uid = self._call(
            service="common",
            method="login",
            args=[self.db, self.login_name, self.password],
            timeout=30,
        )

        if not uid:
            raise OdooJsonRpcError(
                "Authentification Odoo refusée : common.login n'a retourné aucun uid."
            )

        self.uid = int(uid)
        return self.uid

    def execute_kw(
        self,
        model,
        method,
        args=None,
        kwargs=None,
        timeout=60,
    ):
        if self.uid is None:
            self.login()

        rpc_args = [
            self.db,
            self.uid,
            self.password,
            model,
            method,
            args or [],
        ]

        if kwargs is not None:
            rpc_args.append(kwargs)

        return self._call(
            service="object",
            method="execute_kw",
            args=rpc_args,
            timeout=timeout,
        )

    def read_group(
        self,
        model,
        domain,
        fields,
        groupby,
        *,
        offset=0,
        limit=None,
        orderby=False,
        lazy=True,
        timeout=60,
    ):
        kwargs = {
            "offset": offset,
            "orderby": orderby,
            "lazy": lazy,
        }

        if limit is not None:
            kwargs["limit"] = limit

        return self.execute_kw(
            model=model,
            method="read_group",
            args=[domain, fields, groupby],
            kwargs=kwargs,
            timeout=timeout,
        )
