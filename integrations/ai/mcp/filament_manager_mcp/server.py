from __future__ import annotations

from .ams import get_ams_overview
from .events import get_hms_code_info, get_recent_events
from .filament import find_filament_anomalies, get_filament_inventory_summary, list_filament_spools
from .maintenance import get_maintenance_overview
from .print_log import get_print_log_summary, list_recent_print_logs
from .printers import get_printer_overview, get_system_health, list_printers


def create_server():
    from mcp.server.fastmcp import FastMCP

    mcp = FastMCP("filament-manager")
    mcp.tool()(get_system_health)
    mcp.tool()(list_printers)
    mcp.tool()(get_printer_overview)
    mcp.tool()(get_ams_overview)
    mcp.tool()(get_filament_inventory_summary)
    mcp.tool()(list_filament_spools)
    mcp.tool()(find_filament_anomalies)
    mcp.tool()(get_print_log_summary)
    mcp.tool()(list_recent_print_logs)
    mcp.tool()(get_recent_events)
    mcp.tool()(get_hms_code_info)
    mcp.tool()(get_maintenance_overview)
    return mcp


def main() -> None:
    create_server().run()


if __name__ == "__main__":
    main()
