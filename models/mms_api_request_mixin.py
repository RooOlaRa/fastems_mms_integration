import logging

import requests
from odoo import models

_logger = logging.getLogger(__name__)

# Default timeout in seconds for MMS API calls
_DEFAULT_TIMEOUT = 30


class MmsApiRequestMixin(models.AbstractModel):

    _name = "mms.api.request.mixin"
    _description = "MMS API Request Mixin"


    def _make_request(self, backend, method, endpoint, params=None, json=None, **kwargs):
        """
        Execute an HTTP request against the MMS REST API.

        :param backend: mms.backend record
        :param method:  HTTP verb string: 'GET', 'POST', 'PUT', 'DELETE'
        :param endpoint: API path, e.g. '/erp/orders/productionorder'
        :param params:  dict of query parameters
        :param json:    dict payload (serialised to JSON body)
        :returns:       requests.Response
        :raises:        requests.exceptions.RequestException on network error
        """
        url = self._build_url(backend, endpoint)
        headers = self._build_headers(backend)
        auth = self._build_auth(backend)

        _logger.debug("MMS API %s %s params=%s", method, url, params)

        try:
            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                auth=auth,
                params=params,
                json=json,
                timeout=_DEFAULT_TIMEOUT,
                **kwargs,
            )
            self._handle_response(response)
            return response
        except requests.exceptions.Timeout:
            _logger.error("MMS API timeout: %s %s", method, url)
            raise
        except requests.exceptions.ConnectionError:
            _logger.error("MMS API connection error: %s %s", method, url)
            raise

    def _build_url(self, backend, endpoint):
        """Construct the full API URL from backend base URL + endpoint."""
        base = (backend.api_url or "").rstrip("/")
        endpoint = endpoint.lstrip("/")
        return f"{base}/{endpoint}"

    def _build_headers(self, backend):
        """Return the HTTP headers required for all Fastems MMS API requests."""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if backend.auth_method == "apikey" and backend.api_key:
            headers["X-Api-Key"] = backend.api_key
        return headers

    def _build_auth(self, backend):
        """Return a requests-compatible username and password or None."""
        if backend.auth_method == "basic":
            return (backend.api_username or "", backend.api_password or "")
        # ApiKey auth is handled via headers
        return None

    def _handle_response(self, response):
        """
        Log and raise on failure.

        MMS returns HTTP 200 on success and an error code + message on failure.
        """
        if response.ok:
            return
        _logger.warning(
            "MMS API error %s: %s",
            response.status_code,
            response.text[:500],
        )
        response.raise_for_status()
