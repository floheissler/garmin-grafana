"""InfluxDB client wrapper for Garmin data queries."""

import os
from typing import Any
from influxdb import InfluxDBClient


class GarminDB:
    """Wrapper for InfluxDB client with Garmin-specific queries."""

    def __init__(self):
        self.host = os.getenv("GARMIN_MCP_INFLUXDB_HOST", "localhost")
        self.port = int(os.getenv("GARMIN_MCP_INFLUXDB_PORT", "8086"))
        self.database = os.getenv("GARMIN_MCP_INFLUXDB_DATABASE", "GarminStats")
        self.username = os.getenv("GARMIN_MCP_INFLUXDB_USERNAME", "influxdb_user")
        self.password = os.getenv("GARMIN_MCP_INFLUXDB_PASSWORD", "influxdb_secret_password")
        self.timezone = os.getenv("GARMIN_MCP_TIMEZONE", "Europe/Berlin")
        self._client: InfluxDBClient | None = None

    @property
    def client(self) -> InfluxDBClient:
        """Lazy-initialize the InfluxDB client."""
        if self._client is None:
            self._client = InfluxDBClient(
                host=self.host,
                port=self.port,
                username=self.username,
                password=self.password,
                database=self.database,
            )
        return self._client

    def query(self, query: str) -> list[dict[str, Any]]:
        """Execute an InfluxQL query and return results as a list of dicts."""
        try:
            result = self.client.query(query)
            return list(result.get_points())
        except Exception as e:
            raise RuntimeError(f"InfluxDB query failed: {e}") from e

    def get_measurements(self) -> list[str]:
        """Get all measurement names in the database."""
        result = self.client.query("SHOW MEASUREMENTS")
        return [m["name"] for m in result.get_points()]

    def get_field_keys(self, measurement: str) -> list[dict[str, str]]:
        """Get field keys for a measurement."""
        result = self.client.query(f'SHOW FIELD KEYS FROM "{measurement}"')
        return list(result.get_points())

    def test_connection(self) -> bool:
        """Test if the database connection is working."""
        try:
            self.client.ping()
            return True
        except Exception:
            return False


# Global instance
db = GarminDB()
